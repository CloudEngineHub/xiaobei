#!/usr/bin/env python3
"""阿里云百炼（DashScope）HappyHorse / Wan2.7 视频生成。

直连百炼异步任务端点：
  - POST /services/aigc/video-generation/video-synthesis  → 创建任务，返回 task_id
  - GET  /tasks/{task_id}                                  → 轮询 task_status
  - 成功时 output.video_url 即成片下载地址。

模型候选链（每模式一条）：
  happyhorse-1.1-{mode} → happyhorse-1.0-{mode} → wan2.7-{mode}

端点/key 双模式（2026-09 provider 收敛，ds_resolve）：
  - 业务空间（优先）：WORKSPACE_ID + MODELSTUDIO_API_KEY/DASHSCOPE_API_KEY
    → https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1
  - agent plan：否则 AWK_API_KEY → https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1
  - legacy 兼容：都没有但 MODELSTUDIO/DASHSCOPE 在 → 默认 dashscope.aliyuncs.com
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# aigc_common.py 与本脚本同目录（skills/aigc-video-gen/scripts/）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aigc_common import (  # noqa: E402
    TaskFailed,
    die,
    download,
    ensure_safe_output,
    generate,
    get_json,
    log,
    post_json,
    resolve_image,
    resolve_media_url,
    resolve_prev_segment,
)

# ---- 百炼端点与常量 -----------------------------------------------------------

DS_DEFAULT_BASE = "https://dashscope.aliyuncs.com/api/v1"  # legacy 兼容端点
DS_WS_BASE_TEMPLATE = "https://{wsid}.cn-beijing.maas.aliyuncs.com/api/v1"
DS_AGENT_PLAN_BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1"
DS_CREATE_PATH = "/services/aigc/video-generation/video-synthesis"
DS_QUERY_PATH = "/tasks/{task_id}"

# 百炼模型候选链（按价格/可用性优先，每模式一条）：
#   happyhorse-1.1 系列（当前折扣价低于 wan2.7，优先）→ happyhorse-1.0 系列 → wan2.7 系列托底
# generate() 在 TaskFailed / HttpError 时自动沿链 fallback；--model 显式指定时只用该模型。
DS_MODEL_CHAIN = {
    "t2v": ["happyhorse-1.1-t2v", "happyhorse-1.0-t2v", "wan2.7-t2v"],
    "i2v": ["happyhorse-1.1-i2v", "happyhorse-1.0-i2v", "wan2.7-i2v"],
    "r2v": ["happyhorse-1.1-r2v", "happyhorse-1.0-r2v", "wan2.7-r2v"],
}

DS_POLL_INTERVAL = 15
DS_TIMEOUT = 900


def ds_resolve() -> tuple[str, str, str]:
    """解析百炼端点模式。返回 (base, api_key, mode)。

    - 业务空间（优先）：WORKSPACE_ID + MODELSTUDIO_API_KEY/DASHSCOPE_API_KEY
    - agent plan：否则 AWK_API_KEY（token-plan 端点）
    - legacy 兼容：都没有但 MODELSTUDIO/DASHSCOPE 在 → 默认端点（老部署无 AWK_API_KEY 时）
    - 都不可用 → die
    """
    wsid = (os.environ.get("WORKSPACE_ID") or "").strip()
    ws_key = (
        os.environ.get("MODELSTUDIO_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or ""
    ).strip()
    if wsid and ws_key:
        return DS_WS_BASE_TEMPLATE.format(wsid=wsid), ws_key, "workspace"
    if wsid:
        log("WORKSPACE_ID 已配置但 MODELSTUDIO_API_KEY/DASHSCOPE_API_KEY 缺失，尝试 agent plan")
    awk_key = (os.environ.get("AWK_API_KEY") or "").strip()
    if awk_key:
        return DS_AGENT_PLAN_BASE, awk_key, "agent-plan"
    if ws_key:
        return DS_DEFAULT_BASE, ws_key, "legacy"
    die("百炼视频生成凭据未配置：需 WORKSPACE_ID+MODELSTUDIO_API_KEY/DASHSCOPE_API_KEY（业务空间）或 AWK_API_KEY（agent plan）")


# ---- 百炼视频生成 -------------------------------------------------------------

def ds_build_input(args: argparse.Namespace) -> dict:
    inp: dict = {"prompt": args.prompt}

    media: list[dict] = []
    if args.image:
        media.append({"type": "first_frame", "url": resolve_image(args.image)})
    if args.last_frame:
        media.append({"type": "last_frame", "url": resolve_image(args.last_frame)})
    if args.ref_image:
        m = {"type": "reference_image", "url": resolve_image(args.ref_image)}
        media.append(m)
    if args.ref_video:
        m = {"type": "reference_video", "url": resolve_media_url(args.ref_video, "ref-video")}
        media.append(m)
    if media:
        inp["media"] = media
    return inp


def ds_submit(model: str, args: argparse.Namespace, api_key: str, base: str) -> str:
    payload: dict = {
        "model": model,
        "input": ds_build_input(args),
        "parameters": {
            "resolution": args.resolution.upper(),
            "ratio": args.ratio,
            "duration": args.duration,
            "watermark": False,
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    resp = post_json(f"{base}{DS_CREATE_PATH}", payload, headers, timeout=60)
    task_id = (resp.get("output") or {}).get("task_id")
    if not task_id:
        die(f"dashscope submit: no task id in response: {json.dumps(resp, ensure_ascii=False)}")
    return task_id


def ds_poll(task_id: str, api_key: str, base: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base}{DS_QUERY_PATH.format(task_id=task_id)}"
    deadline = time.time() + DS_TIMEOUT
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        resp = get_json(url, headers, timeout=30)
        out = resp.get("output") or {}
        status = out.get("task_status", "")
        log(f"dashscope poll #{attempt}: status={status}")
        if status == "SUCCEEDED":
            video_url = out.get("video_url")
            if not video_url:
                die(f"dashscope succeeded but no video_url: {json.dumps(resp, ensure_ascii=False)}")
            return video_url
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise TaskFailed(
                f"dashscope task {status}: {out.get('code', '')} {out.get('message', '')}"
            )
        time.sleep(DS_POLL_INTERVAL)
    die(f"dashscope timed out after {DS_TIMEOUT}s (task {task_id})")


def ds_candidates(args: argparse.Namespace, mode: str) -> list[str]:
    # Mode-level capability checks (apply to every model in the chain)
    # happyhorse 系列最短 3 秒；wan2.7 托底同链，统一要求 ≥3（脚本规划已遵守）
    if args.duration < 3:
        die("百炼视频生成最短 3 秒；请将 --duration 提到 ≥3 或拆分片段")
    # i2v 仅首帧，不支持首+尾帧
    if mode == "i2v" and args.last_frame:
        die("i2v 不支持首+尾帧（仅首帧）；请去掉 --last-frame")
    # r2v 仅参考图，不支持参考视频、不支持首帧
    if mode == "r2v" and args.ref_video:
        die("r2v 仅支持参考图（--ref-image）；不支持 --ref-video")
    if mode == "r2v" and args.image:
        die(
            "r2v 仅支持参考图（--ref-image）；"
            "不要传 --image 或 --prev-segment（r2v 不收首帧）"
        )
    return list(DS_MODEL_CHAIN[mode])


# ---- 调度 --------------------------------------------------------------------

def run_one(platform: str, model: str, args: argparse.Namespace, api_key: str) -> str:
    """Submit + poll for a single DashScope model. Returns video URL or raises."""
    base, _key, _mode = ds_resolve()
    task_id = ds_submit(model, args, api_key, base)
    log(f"dashscope task submitted: {task_id} (model={model} base={base})")
    return ds_poll(task_id, api_key, base)


def cmd_video(args: argparse.Namespace) -> None:
    if args.duration < 3 or args.duration > 15:
        die("--duration 必须在 3–15 秒之间")

    # --prev-segment: 抽取上一段末帧作为本段首帧（人物故事首尾帧对齐）
    resolve_prev_segment(args)

    base, api_key, provider_mode = ds_resolve()

    has_ref = bool(args.ref_image or args.ref_video)
    has_i2v = bool(args.image or args.last_frame)
    mode = "r2v" if has_ref else ("i2v" if has_i2v else "t2v")

    candidates = [args.model] if args.model else ds_candidates(args, mode)

    output_path = ensure_safe_output(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log(
        f"platform=dashscope provider={provider_mode} mode={mode} candidates={candidates} "
        f"duration={args.duration}s ratio={args.ratio} resolution={args.resolution}"
    )
    video_url = generate("dashscope", candidates, args, api_key, run_one)
    download(video_url, output_path)

    meta = output_path.with_suffix(".json")
    meta.write_text(
        json.dumps(
            {
                "platform": "dashscope",
                "provider_mode": provider_mode,
                "mode": mode,
                "model_candidates": candidates,
                "duration": args.duration,
                "ratio": args.ratio,
                "resolution": args.resolution,
                "video_url": video_url,
                "file": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[done] video saved: {output_path}")
    print(f"[done] metadata:    {meta}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aliyun DashScope (HappyHorse / Wan2.7) video generation."
    )
    sub = parser.add_subparsers(dest="command")

    # ── 默认子命令：video ──
    p_video = sub.add_parser("video", help="视频生成(默认,可省略 video 子命令)")
    p_video.add_argument("--prompt", required=True, help="画面+音频描述（声画同出）")
    p_video.add_argument("--image", default=None, help="首帧图片：URL 或本地路径（→ i2v）")
    p_video.add_argument("--prev-segment", default=None, dest="prev_segment",
                         help="上一段视频本地路径：脚本自动抽取其末帧作为本段首帧（人物故事首尾帧对齐）。与 --image 互斥")
    p_video.add_argument("--last-frame", default=None, dest="last_frame", help="尾帧图片：URL 或本地路径（i2v 首尾帧）")
    p_video.add_argument("--ref-image", default=None, dest="ref_image", help="参考图片：URL 或本地路径（→ r2v，角色/主体一致性）")
    p_video.add_argument("--ref-video", default=None, dest="ref_video", help="参考视频 URL（→ r2v，需公网 URL）")
    p_video.add_argument("--duration", type=int, default=8, help="时长（秒），默认 8，百炼范围 3–15")
    p_video.add_argument("--ratio", default="9:16", help="宽高比，默认 9:16")
    p_video.add_argument("--resolution", default="720P", choices=["720P", "1080P"], help="分辨率，默认 720P")
    p_video.add_argument("--model", default=None, help="指定模型 id（关闭候选链 fallback）")
    p_video.add_argument("--output", required=True, help="输出 MP4 路径（相对工作区，须在 output_videos/tmp/fragments/artifacts 或 <platform>/outputs/ 下）")

    return parser


def main() -> None:
    parser = build_parser()

    # 向后兼容：无子命令时，把全部 argv 当成 video 子命令的参数
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["video"] + argv

    # video 子命令可省略：如果第一个 token 不是已知子命令，默认走 video
    known_subcommands = {"video"}
    if argv and argv[0] not in known_subcommands:
        argv = ["video"] + argv

    args = parser.parse_args(argv)
    cmd_video(args)


if __name__ == "__main__":
    main()
