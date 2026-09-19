# 抖音发布：登录与异常处置

`douyin-note-publish` 与 `douyin-video-publish` 共用本流程、login-manager 和唯一持久化 session `douyin`。每次发布先读本说明。发布工具不负责扫码登录，也没有 `login` 子命令；`login-manager --platform douyin` 负责用户登录后的导出与验证，不会代替用户登录。

## 1. 打开创作者上传页并判断登录态

按本次形态执行一个命令：

- 图文：`douyin-note-publish open-page`
- 视频：`douyin-video-publish open-page`

用 `camoufox-cli --session douyin --persistent --json snapshot -i` 查看页面，必要时截图判断：

- 用户头像 / 用户名及创作者上传界面已出现，无登录遮挡 → 继续对应工具的 `run`。
- 跳登录页或出现要求登录的弹窗 → 进入下方登录流程，暂不上传。
- 页面尚未加载、元素缺失或浏览器报错 → 保留错误，排查页面或环境；不能只凭无头像或 `open-page` 的 `ok=true` 判定登录成功/失效。

浏览器持久化 profile 才是发布登录态来源；中央 cookie 文件存在、HTTP 探活通过均不能替代创作者页面检查。视频工具没有完整的自动登录判断；图文工具可识别跳登录页，页面内登录弹窗仍由 agent 检查。

## 2. 首次登录或登录失效

1. 先读 `login-manager` 技能，停止当前发布步骤，复用同一 session 有头打开：

   ```bash
   camoufox-cli --session douyin --persistent --headed --json open "https://creator.douyin.com/creator-micro/content/upload?enter_from=dou_web"
   ```

2. 告知用户在窗口里手动完成抖音创作者中心登录，等待用户确认；不盲轮询、不自行扫码。不在 heartbeat / isolated 定时任务里启动交互登录，那里只记录并跳过。
3. 用户确认完成后执行：

   ```bash
   login-manager --platform douyin
   ```

   该命令导出 cookie 与 UA、验证、成功后写中央存储并 close session。失败时保留窗口，按 login-manager 的错误处理，不循环导出或重登。
4. 成功后重新执行第 1 节对应的 `open-page`，由 agent 确认创作者页面已登录，再按第 3 节选择恢复步骤。默认发布以无头方式重新启动磁盘 profile。

## 3. 运行中异常与恢复

| 现象 | 操作 |
| --- | --- |
| 上传 / 填表前明确未登录，或 exit 2 | 停止发布，走第 2 节；成功后重新检查页面与未发布内容，再继续尚未执行的步骤 |
| 已点击发布，之后登录失效 / 超时 / 取链失败 | 发布结果待核实。重登后先到管理页核实；图文可用 `douyin-note-publish get-note-link --title "完整标题"` 补取链接。不得直接重跑 `run` / `publish` |
| login-manager exit 2（导出验证未通过） | 提醒用户人工核实账号与当前页面，停止本轮自动恢复；不反复重登 |
| `session douyin 正忙` | 等已有任务完成后再操作，不起第二个 session，也不关闭别人的任务 |
| 找不到 input / 按钮，页面未跳登录 | 保留 DOM / 超时错误，检查页面；不把所有浏览器错误当成登录失效 |
| 需要实名认证 / 账号验证 | 交用户在原窗口处理，不自动绕过 |
| 显示环境异常或风控限流 | 显示问题报告并停止，不改 DISPLAY 或搭显示栈；风控停止，30 分钟内不重试 |

## 4. 会话纪律

- 登录阶段的直接浏览器命令一致带 `--persistent --headed`。不要在等待用户登录时调用默认无头发布命令，以免 daemon 切模式重启窗口。
- 图文发布需要用户监督时，所有图文子命令传 `--headed`，直接 camoufox-cli 操作也保持有头。视频发布 wrapper 默认无头：先完成 login-manager 导出关闭，再回无头发布流程。
- 严禁 `cookies import` 或另建临时 session 导入 cookie 造会话；不在日志、作品目录或代码里记录 cookie。
- `run` 完成后关闭 session。分步操作结束或放弃时关闭自己占用的 session；login-manager 失败保留的窗口交用户处理，不擅自关闭。
