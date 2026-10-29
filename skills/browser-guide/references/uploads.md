# 本地媒体上传

只适配已确定素材的上传路径；发布、登录和提交遵循对应平台技能。

- 当前 `xiaobei_browser` 接受受管 uploads 目录内的文件，以及实际 `<stateDir>/media/inbound/` 的**直接子文件**。inbound 的嵌套目录不符合规则；支持的 `media://inbound/<文件名>` 也只指向直接子文件。以当前工具 schema、文件策略及返回的根目录为准，不放宽策略。
- 正式素材在允许位置时直接使用；路径被拒时用下面的 wrapper 复制最终版本。它保留源文件，为本任务生成唯一文件名，并核对大小与 SHA-256；任一副本失败时清理本次已生成副本。默认按 `OPENCLAW_STATE_DIR`（未设时 `~/.openclaw`）解析 inbound；自定义位置用 `--inbound-root` 指定工具声明的实际根目录。

```bash
browser-guide stage-upload /绝对路径/video.mp4 /绝对路径/cover.jpg
```

将返回的 `files[].path` 原样交给 `xiaobei_browser action="upload"` 的 `paths`。持有同一 session、targetId 和 lease；`inputRef` 或 `selector` 必须来自当前页面。视频与封面 input 同时存在时限定已核实的 accept 等属性，不用会多命中的裸选择器。

路径被拒表示还没选文件，修正位置即可。工具接受文件只说明文件已选择；继续核对页面上传、转码、封面和表单，不能据此声称发布成功。提交结果未知时先查结果，不重放发表。

正式作品仍按平台归档；记录源版本、返回的副本路径与发布结果。按保留约定只删除本任务副本，不清空 inbound。workspaceOnly 等文件策略仍可能拒绝暂存路径；此时报告限制，交 IT 处理，不移动根目录或改策略绕过。
