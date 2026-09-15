# wx_mp — 微信公众号平台运营文件夹

该平台全部运营数据存于此，子目录专款专用、不混放：

| 子目录 | 内容 |
|--------|------|
| `ref/` | 参考材料（对标文章采样、转录文本等） |
| `outputs/` | 文章产出（每篇一个 `<article-name>/`：article.md、配图、封面、dna-meta.json） |
| `dna/` | DNA 运行资产（每 `<dna-id>/`：reports / dna 文档 / template / evals） |
| `calibration/` | 校准与复盘数据（baseline、受众画像、对标记录、平台状态） |
| `wenyan-theme/` | 排版主题模板存放（`wx_mp/wenyan-theme/`） |

`calibration/` 默认含 `audience.md`（受众画像）与 `platform-state.json`（平台状态）；其余文件（对标记录等）由相应 workflow 按需生成。

数据存储总约定见工作区 `AGENTS.md`「数据存储」段。
