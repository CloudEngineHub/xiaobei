# business_knowledge/ — 业务知识与支撑材料

业务知识正文固定为 `business_knowledge.md`，是本目录内的普通文件；从 workspace 根读取时使用 `business_knowledge/business_knowledge.md`。

正文和支撑材料统一由 main agent 维护，落盘前征得用户同意。其他 crew 只共享 `business_knowledge/` 目录软链，不另建正文文件软链或副本。

```text
business_knowledge/
├── business_knowledge.md   # 业务知识正文
├── README.md              # 本说明
├── pricing-2026.png       # 价目表截图
├── case-xxx.md            # 案例附录
└── ...
```

正文内的相对链接以本目录为基准，例如 `[价目表](./pricing-2026.png)`。图片、PDF、合同模板、资质等引用材料放在本目录；市场运营素材仍放在 workspace 的 `campaign_assets/`。
