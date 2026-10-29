---
name: demo-send
description: >
  Send configured product demo material when customers ask about concrete
  usage, want to understand the product, or need a visual reference.
---

# Demo material

在同级 `config.json` 的 `media` 字段配置演示材料的本地绝对路径或 HTTPS URL。字段为空时，先让 main agent 配置实际素材；不要猜测文件名、路径或链接。

使用所有 channel 共用的媒体发送格式，当前会话可省略 target：

```
message(action="send", media="<config.json 中的 media>")
```

可以在同一次调用中使用 `message` 参数附带说明文字。发送前不要先输出另一份相同的介绍；工具完成后再询问客户的具体需求或应用场景。

`queued` / `submitted` 表示提交成功，不能据此宣称已送达。遇到 `failed` / `unknown` 时保留回执并查询结果，不盲目重新发送，不把内部错误详情直接转发给客户。
