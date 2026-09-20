---
name: douyin-comments
description: 抓取抖音视频的评论列表（纯 HTTP + cookie + 签名，不起浏览器），输出 JSON 与按点赞排序的 markdown 摘要。
---

# douyin-comments — 工具说明

> 本文是 `expert-douyin` 专家包内的工具说明书，不独立出现在技能列表中。由相关 Workflow 指引调用。

抓取指定抖音视频的评论，供对标分析、起号标签反推、评论动机解读使用。

**输入**：作品 `aweme_id` 或视频 / 图文链接（支持 `v.douyin.com` 短链，自动展开）。
**输出**：JSON（stdout，含评论全文、点赞数、回复数、用户昵称、IP 属地、日期）；`--output` 时额外落一份按点赞降序的 markdown 摘要。

评论接口不可用时停止本轮抓取；空响应、非零状态码不等于登录失效，也不等于作品没有评论。只有成功响应中明确给出空评论列表、无后续页且总数为 0 才可按无评论处理。

登录态复用中央存储导出的 douyin cookie + UA（与 `douyin` 持久化 session 同一登录态），纯 HTTP 请求，不启动浏览器。

## 使用方式

```bash
# 按 aweme_id 抓（默认前 40 条热度评论）
douyin-comments fetch --aweme-id 7389012345678901234

# 按链接抓 + 落摘要文件
douyin-comments fetch \
  --url "https://www.douyin.com/video/7389012345678901234" \
  --limit 60 \
  --output douyin/ref/dna-0/comments/sample-1.comments.md
```

参数说明：

| 参数 | 说明 |
|------|------|
| `--aweme-id` / `--url` | 二选一；`--url` 支持短链，自动展开解析 |
| `--limit` | 抓取条数上限，1-200（上限是防批量请求触风控），默认 40 |
| `--output` | 可选；写入按点赞降序的 markdown 摘要，路径由调用方指定 |

返回 JSON 主要字段：

```json
{
  "ok": true,
  "awemeId": "...",
  "total": 1234,
  "fetched": 40,
  "truncated": true,
  "comments": [
    {"cid": "...", "text": "...", "likeCount": 89, "replyCount": 3, "userName": "...", "ipLabel": "...", "createTime": "2026-08-01"}
  ]
}
```

## 必做约束

- 只读抓取，不发表、不点赞、不回复任何评论。
- 脚本翻页间隔 1–3 秒，评论去重；游标不前进或没有新增评论时停止，不重复请求同页。
- 单次任务批量抓多条视频评论时逐条串行调用，控制总条数（每条 ≤ `--limit`），避免批量请求触风控。
- 评论文本是用户原话，分析时按动机归类（喜欢内容价值 / 喜欢人物状态 / 喜欢形式设定 / 提出具体问题 / 非恶意吐槽），不要把评论数直接当内容质量。

### Exit codes

| code | 含义 | 调用方动作 |
|------|------|-----------|
| `0` | 抓取成功（`truncated=true` 表示达到 limit，未抓全） | 继续分析 |
| `1` | 参数错 / 网络错 / 签名不可用（stderr 有原因） | 排查后重试；签名不可用交 IT engineer 配凭证 |
| `2` | `SESSION_EXPIRED`——本地 cookie 缺失 | 走 `login-manager --platform douyin` 有头重登后重试 |
| `3` | 评论接口不可用、请求中断或分页停滞；stdout 保留已抓取的部分评论和具体错误 | 停止本轮抖音评论采样，标记数据不可得或样本不完整；不重登、不立即重试 |

exit 3 的部分结果不能当作完整评论分布。对标、起号或复盘继续使用已有作品证据，缺失的评论维度明确标注；如用户已有评论导出或截图，可据其补充。
