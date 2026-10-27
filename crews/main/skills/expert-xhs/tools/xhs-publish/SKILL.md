---
name: xhs-publish
description: 通过 Creator 本地 HTTP 会话发布小红书图文和视频笔记，并管理 Creator 扫码登录。
---

# 小红书发布

本工具由 `expert-xhs` 的发布 Workflow 调用。客户端负责 Creator HTTP 请求、媒体上传和发布，签名由 OFB Relay 提供（需配置 `OFB_KEY`）；`xhs-engagement` 复用同一登录态。会话存于 `~/.openclaw/logins/xhs-creator-local.json`（0600），Cookie 和会话状态持久化。只要 Cookie 有效，后续命令直接复用，不必每次扫码。

## 登录流程

1. 发布前运行 `xhs-publish check`。退出码 0 表示有效；2 表示缺少会话或明确认证失效；1 表示接口或环境故障，先排查。
2. 仅在需要重新登录时运行 `xhs-publish login`。它启动后台扫码任务并返回 `qr_path`，默认图片在 `/tmp/qr-xhs.png`，权限 0600。若二维码尚未生成，按返回错误排查或稍后重试；不要并发启动多个登录。
3. 使用当前会话的图片发送工具，把 `qr_path` 指向的 PNG 作为图片发给用户，然后**停止并等待用户回复已扫码/已确认**。脚本只生成图片，不代发飞书或微信消息。不要仅发路径给远程用户，也不要把登录二维码发给其他人。
4. 用户确认后运行 `xhs-publish login-confirm`。退出码 0 且 `ok: true` 才算登录成功；`LOGIN_PENDING` 表示手机端确认还没完成，稍后再查；二维码过期或失败时重新运行 `login`，再发送新图片。登录成功后会话原子落盘；旧会话只有新登录验过时才替换。

二维码图片是短期临时文件，登录结束会删除。后台日志在 `~/.openclaw/logs/xhs-creator-login.log`；不向用户转发日志。`xhs-publish check` 使用签名 `user/info` 验证，不反复扫码排查非认证错误。

登录日志与 `xhs-creator-observe.jsonl` 均按 5 MiB 轮转，各保留 `.1`–`.3` 三份备份，连同当前文件每组最多约 20 MiB；后台登录执行期间也会持续轮转。

## 彻底清空本地账号与换号

用户要求彻底清空本地小红书账号时，先结束小红书业务请求和后台扫码任务，再删除创作者端 `~/.openclaw/logins/xhs-creator-local.json` 与采集端 `~/.openclaw/logins/xhs-pc-local.json`、对应登录状态及二维码、含凭据的备份；设置了 `XHS_CREATOR_SESSION_FILE` 或 `XHS_PC_SESSION_FILE` 时清理其实际路径，保留业务数据和其他平台会话。换号时先结束旧扫码任务，再按本节流程用目标账号重新登录；需要保留旧号时先将其会话以 0600 权限备份，不保留时先清空。创作者端与采集端独立登录，整体换号还须按 `xhs-hunter` 的登录流程切换采集端，确认两端均由目标账号扫码，并分别运行 `xhs-publish check` 和 `xhs-hunter check` 验证；只重登一端不会切换另一端。

## 发布

```bash
xhs-publish --mode image --title "标题" --body @/绝对路径/body.txt --images /绝对路径/1.png /绝对路径/2.png
xhs-publish --mode video --title "标题" --body @/绝对路径/body.txt --video /绝对路径/video.mp4 --cover /绝对路径/cover.jpg
# 笔记含 AI 合成内容时，在对应发布命令末尾加 --ai-declaration
```

先把已确认的纯正文和话题写入 UTF-8 `body.txt`，使用 `--body @/绝对路径/body.txt`；路径含空格时把整个参数加引号：`--body "@/绝对路径/作品目录/body.txt"`。脚本读取文件后校验长度、整理话题，保留文件中的真实换行和有意写下的 `\n`；文件缺失、不是普通文件或不是 UTF-8 时返回 `BODY_FILE_INVALID`，不提交。不要把含标题、分节说明的 `note.md` 整份作为正文，不用 `$(cat ...)` 或把多行正文拼进命令。短正文仍可直接传文字；仅此模式兼容归一化字面量 `\n`。以 `@` 开头的参数一律按文件路径处理。

标题 1–20 字，正文 1–1000 字；图文需 1–18 张图片，视频需 `--video`。`--topics` 可补充话题，合计最多 10 个；`--private` 设为仅自己可见。笔记含 AI 合成内容时加 `--ai-declaration`，发布请求会带上创作者端的“笔记含 AI 合成内容”声明；纯实拍内容不加。正文中的 `#话题` 自动整理为 Creator 可识别的内联话题格式。

发布前让用户确认标题、正文、图片顺序及可见性。提交成功必须同时有 `ok: true` 和 `note_id`，再记录返回的 `url`。接口明确拒绝时根据错误码处理。`TITLE_INVALID` 在本地校验阶段返回，尚未上传或提交；把标题改到 1–20 字并确认后可重新调用。

发布 Workflow 负责判断内容是否需要 AI 声明，并在调用发布命令时传入 `--ai-declaration`。

视频转码与笔记提交分别判断：`readiness.state:ready` 表示查询返回就绪证据；Creator 会话缺少 www 查询认证时允许服务端异步转码提交，但返回 `readiness_unknown/auth_unavailable`。网络、服务错误、空数据和持续 pending 不按 ready 处理，提交前停止并返回 `VIDEO_READINESS_UNCONFIRMED`、`submission_attempted:false`。`accepted:true` 与作品 ID 只证明平台接受，`public`/`playable:null` 仍需核实；不要因可播放未知自动重发。

## 提交结果不确定时

`SUBMISSION_UNKNOWN`（包括 `curl: (28) Operation timed out`）表示无法确认结果；`SUBMISSION_UNCONFIRMED` 表示平台返回成功但缺少作品 ID。两者都不能当作发布失败，**不要自动重发**，也不要因创作者列表未出现目标笔记就重发。

- 用现有 `xhs-engagement list` 查看当前账号的已发作品。候选笔记须结合账号、标题和实际内容核实；同名多条时不能自动取第一条。确认目标笔记后保留真实作品 ID 和链接，不再次提交。
- 列表可能滞后，没查到仍属于待核实。停止发布重试，请用户在 App 核对（必须用app，不可同时登陆网页端创作者后台，会造成平台风控），提供目标笔记链接；用户确认已发布时按该链接恢复记录。只有用户核实确实未发布并明确要求重试，才重新提交；触发风控时继续遵守 `expert-xhs` 的限频和停手规则。
- 确认成功后的记录沿用 `published-track`，先查询是否已有对应记录。补录使用原作品目录、实际发布日期和发布账号，内容类型与原图文 / 视频一致；历史发布显式传 `--publish-date`，不要把补录日当作发布日。同一目录和发布日的 `record` 会更新原行；不要新造目录或日期造成重复记录。分发状态按实际需求填写，不因超时恢复就统一设为无需分发。

操作结果写入 `~/.openclaw/logs/xhs-creator-observe.jsonl`：`SUBMISSION_UNKNOWN` 对应 `outcome: "unknown"`，`SUBMISSION_UNCONFIRMED` 对应 `outcome: "unconfirmed"`，不含正文或 Cookie。日志只说明本次请求结果，不能代替平台侧发布核实。

当前 HTTP 单次请求超时为 120 秒，媒体上传与发布提交均使用该设置；这不是整轮发布的总时限。若仍报约 15000 毫秒超时，请 IT engineer 核查实际加载版本和外层超时限制，不要由发布智能体临时改共享库来反复重试。即使延长超时，结果不确定时仍按上面的核查规则处理。
