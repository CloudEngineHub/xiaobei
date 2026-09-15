---
name: collage-broll
description: 纸拼贴 B-roll 的原子工具——环境自检与 Gate 3 批量 i2v 视频生成调度。
---

# collage-broll — 工具说明

> 本文是 `expert-video` 专家包内的工具说明书，不独立出现在技能列表中。制作流程（视觉隐喻 → 静帧 → 视频三道闸门）由包内 Collage B-roll Workflow 编排。

**用途**：代理纸拼贴 B-roll 的两个脚本，让 agent 走 PATH 调用、零路径拼接。

**输入 / 输出**：

| 子命令 | 入 | 出 | 退出码 |
|--------|----|----|--------|
| `collage-broll check-setup` | 无（读环境变量与 PATH） | stdout 逐项 PASS/FAIL | 0 全通 / 1 有缺项 |
| `collage-broll gate3` | `--batch <project-dir>/gen-jobs.json`（每条含 prompt / first_frame / last_frame / output / ratio / resolution / duration），可选 `--dry-run` | 逐条调公共 `aigc-video-gen` i2v 落 MP4 + decisions.log | 0 全通 / 1 参数错、jobs 文件不存在或格式错、`aigc-video-gen` 不在 PATH / 2 部分 job 失败（stderr 报失败清单，已跑通的保留） |

**调用方式**：

```bash
collage-broll check-setup
collage-broll gate3 --batch output_videos/<slug>/gen-jobs.json --dry-run
collage-broll gate3 --batch output_videos/<slug>/gen-jobs.json
```

**注意事项**：

- `gate3` 串行调度：视频生成是异步轮询任务，并行会撞平台并发限。
- `gen-jobs.json` 的 `output` 必须是相对 workspace 根、且落在 `output_videos/` 下的路径（`aigc-video-gen` 的 ensure_safe_output 要求）；调用时 workdir 必须是 Content Producer workspace 根。
- 依赖：`ffmpeg` / `ffprobe` / Python ≥ 3.10；`AWK_API_KEY`（Gate 2 静帧）；`MODELSTUDIO_API_KEY` 或 `DASHSCOPE_API_KEY`（百炼）或 `AWK_GEN_KEY`（火山）。缺项由 `check-setup` 报出，补齐属 IT engineer 职责。
- 模型候选链 fallback 与 decisions.log 由 `aigc-video-gen` 自带，本工具不重复实现。
