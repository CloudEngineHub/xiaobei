# xiaobei-browser Gateway adapter

基于 OpenClaw 2026.10.4。`patches/01-*.patch` 只替换内置 browser 工具工厂；`files/xiaobei-browser.adapter.ts` 和对应上游测试材料由补丁入口复制到 `extensions/browser/src/`。上游 browser CLI、Gateway 管理方法、dashboard、Chrome relay、node 与 sandbox 源码保留，agent 工具仅公开当前 Camoufox runtime 能执行的动作。

| 工具动作 | runtime 对应与限制 |
| --- | --- |
| status / profiles | 只读查询；不启动 daemon，profiles 列出现役 session |
| start / stop | 共享 client 启停；保留配置中的 proxy/locale/viewport；不自动驱逐旧会话 |
| tabs / focus / close | 稳定 tabId；校验目标；已在当前 tab 时不切换，以保留 refs |
| open / navigate | 当前 tab 导航，仅接受无内嵌凭据的 HTTP(S) URL |
| snapshot / text | ARIA 快照和文本；对模型输出加外部不可信内容标记 |
| screenshot / pdf | PNG 图像内容块或受文件策略约束的路径；PDF 为栅格化全页截图 |
| upload | 复用上游上传路径白名单，再检查工具文件策略 |
| act | click / type / press / hover / select / fill / wait / evaluate / close；type 替换输入，select 仅单个 option label |
| lease | acquire / renew / wait / release；多步骤持有 token，人工登录使用 wait |

普通站点使用持久化 `default`；平台 session 以对应技能约定为准。工具单次调用自动持有 lease，目标切换和操作属于同一所有权窗口；调用方传入 leaseToken 时保留该所有者的 lease。超时/中途取消不重放动作；已发出的操作可能完成，应先核实结果。

adapter 从产品目录 `browser/dist/client/index.js` 动态导入共享 client，不依赖 cwd、全局 npm、CLI 软链或 Unix socket 命名。浏览器包从自己的 node_modules 解析依赖。安装由 `scripts/install-browser.mjs` 完成，兼容 CLI 入口仍名为 camoufox-cli。

sandbox、禁止 host 控制、原生 run-bound tab 均拒绝执行。browser SSRF policy 仅在单独声明 `dangerouslyAllowPrivateNetwork: true` 时匹配运行时当前网络能力；含其他字段的显式策略拒绝执行，不能丢弃限制来放行。runtime 尚无完整网络策略拦截契约。evaluate 遵守开关，workspace-only 文件策略下禁用。未支持的 dashboard/remote-node、frame、下载、dialog、拖拽、坐标点击等参数/动作不在工具 schema 中，不会暗中切到 Chrome。原生 Windows/macOS、特殊 DOM、平台业务仍需验收，本机切换记录见 `docs/5.8-upgrade-execution-plan.md`。

测试源码在 `files/*.test.ts` 是上游补丁材料；本机其他回归/夹具放仓根 ignored `test/`。将材料复制到引擎后，用其 `test/vitest/vitest.extension-browser.config.ts` 运行 adapter 测试。开发验证不等于应用部署脚本或完成业务收发验收。
