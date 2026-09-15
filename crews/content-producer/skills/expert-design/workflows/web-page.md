# Workflow：Web Page（完整网页 / 落地页设计）

任务类型：产品介绍页、活动落地页、团队介绍页、404 页等完整网页。Step 1/2/3/6/7 按 `expert-design` SKILL.md 的通用骨架执行，本文只写本类型的 brief 必含字段与 Step 4/5 差异。

## Step 2：brief 必含字段

- 页面类型（产品介绍页 / 活动落地页 / 团队介绍 / 404 页…）
- 页面清单与信息架构（Sections 列表，按顺序）
- 交互功能范围（纯静态展示 / 含表单 / 含轮播 / 含锚点导航…）
- 风格参考（品牌名或描述词，供 Step 3 `design-full pick` 使用）
- 是否需要深色模式
- 品牌约束（品牌色、字体、Logo——从 MEMORY.md 或甲方素材取，注明绝对路径）
- 文案来源：甲方给终稿则逐字使用；未给时明确由谁补，不得自造卖点与数据

## Step 4：素材

页面所需配图 / 背景图 / 参考图：`pexels-footage` / `pixabay-footage` 优先，`siliconflow-img-gen` 备选，全部落 `source/` 并记 `prompts.json`。

## Step 5：编写

- CSS custom properties 定义设计 token，严格遵循 DESIGN.md
- 语义化标签（header / main / section / footer）
- 响应式：min-width 768px / 1024px 断点
- hover / focus / active 状态完备
- 图片引用 `source/` 中的素材，不热链外站

## 交付

HTML/CSS 文件落 `output/`，归档更新 `index.md`；回报绝对路径 + Step 6 视觉 review 结论 + 遗留问题（如缺文案、缺真实数据占位）。
