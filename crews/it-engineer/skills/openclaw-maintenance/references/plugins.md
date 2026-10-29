# 插件生效与有头浏览器

先用当前会话的原生 plugins 工具或已安装 CLI 检查插件是否安装、启用、被允许并实际加载。`channels.<id>` 有配置不证明插件已运行；也不要把缺 `plugins.entries` 段一概解释为未启用，默认行为依插件来源和当前配置而定。渠道开通继续使用 `awada-channel-setup` / `work-channel-binding`。

`openclaw plugins reload <pluginId> --json` 用于已授权的插件替换。检查结果的 generation、warnings、restartRequired 和实际运行状态：

- 成功且无需重启，再核对工具/命令注册与所需渠道状态。
- 返回 restartRequired 时，新注册状态不证明编辑后的代码已加载；在已授权范围内按部署的服务管理器重启。Linux user systemd、macOS、Windows、Docker 的入口不同，不硬编码本机 unit。
- queued behind retained/admitted work 或 drain 超时，表示替换可能未完成，旧代可继续服务。核对未结束的工作；只有确认会自然结束且任务预算允许时才等待，不无界 `--wait` 或反复 reload。不能据此宣布“所有运行中插件必须重启”。不通过 disable/enable 强退来绕过持有任务。

Awada 同名本地命令的 handler 内容每次调用会重读 commands.json；新增/删除名称或注册元数据需要正常插件替换。`openclaw gateway call commands.list` 可核对注册；静默成功的 handler 按原生回复协议返回 `{"text":"NO_REPLY"}`，不要用 `{}` 引发无可见回复兜底。不要为验证命令而触发真实客户动作。

`openclaw channels status` 与主日志可协助核对加载及连接，默认 warn 日志不记录全部成功 INFO 行。插件渠道的 `channels logs --channel` 若报 Unknown channel，先核对当前 CLI 的渠道目录支持，不据此认定渠道配置消失。配置、连接与实号业务回执分别报告；Awada 业务能力和交付依对应技能，不检查或选择底层平台代次。

有头浏览器由 xiaobei-browser 插件 broker 管理，正常情况下可跨 exec 保留。`BROKER_REQUIRED` 核对插件服务；不自行起 systemd/nohup daemon 绕过。`MODE_CONFLICT` 表示同名 session 参数冲突，先确认无他人任务/人工登录再按 browser-guide 显式 stop 重开。窗口关闭是否正常看对应 `weibo-hunter` / `x-hunter` / `tiktok-hunter` / `xhs-hunter` 等登录流程结果，不随意新建 probe session。确需验证跨调用存活时只检查已授权的本任务 session；profile 持久化不要求进程永久存活。不要按进程年龄批量杀浏览器。

`PROFILE_RESET_REQUIRED` 不等于普通重登提示。旧 v1、损坏身份或缺身份的已登录 profile 按项目 browser/ 的恢复约定，在授权范围内整体归档后重新登录；不复制指纹模板、导回旧 cookies 或自行删除登录态。浏览器版本和资产锁以 browser/ 的当前配置为准，不在记忆模板再维护一套版本表。
