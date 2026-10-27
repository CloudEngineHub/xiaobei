---
name: liveportrait
description: expert-video 的旧数字人任务续查兼容入口。新任务使用包内 avatar 工具。
---

# 旧任务续查

新任务读 `../avatar/SKILL.md` 并用 `avatar generate`。此入口只恢复既有任务，不再向旧模型提交生成。

```bash
liveportrait resume --job /absolute/render/presenter.liveportrait.json
```

保留真实模型字段与原时长结果；`SUCCEEDED` 且 `timing_pass=false` 的记录不得手改为通过。已下载的视频与原声哈希、时长验收通过后才能参与后续合成。
