# Workflow：App UI（APP / 产品界面原型设计）

任务类型：移动 APP、Web APP、管理后台、SaaS 面板的界面原型。Step 1/2/3/6/7 按 `expert-design` SKILL.md 的通用骨架执行，本文只写本类型的 brief 必含字段与 Step 3/5 差异。

## Step 2：brief 必含字段

- 产品类型（移动 APP / Web APP / 管理后台 / SaaS 面板…）
- 核心页面清单（登录 / 首页 / 列表 / 详情 / 设置…）
- 交互模式（导航方式、手势支持、状态管理）
- 数据形态：真实数据样例或占位规则（不得自造业务数字）
- 风格参考与品牌约束

## Step 3 之后：另写 DESIGN.md 设计规范

在设计系统选定结果基础上补全界面专用规范：

- 色彩系统（语义色名 + hex + 用途：primary / secondary / surface / error…）
- 字体系统（font-family + 层级表：display / heading / body / caption / overline）
- 间距系统（4 / 8 / 12 / 16 / 24 / 32 / 48px 基准）
- 组件样式规范（Button / Input / Card / Nav / Modal / Toast 等，含各状态）
- 阴影 / 圆角 / 动效规范

## Step 5：编写关键页面 HTML + CSS 原型

- 严格遵循 DESIGN.md 的 token
- 移动 APP 界面按 375px 基准移动优先；后台/面板按桌面断点
- 交互状态齐全：hover / focus / disabled / loading
- 空态、错误态、加载态至少各给一个页面示例

## 交付

DESIGN.md + 所有页面 HTML/CSS 落 `output/`；回报绝对路径 + 页面清单 + 视觉 review 结论 + 未覆盖的状态说明。
