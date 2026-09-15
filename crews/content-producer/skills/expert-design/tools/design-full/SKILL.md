---
name: design-full
description: 平面设计原子工具——建任务工作区与 brief 模板（init）、从内置设计系统库匹配风格（pick）。
metadata:
  openclaw:
    emoji: 🎨
    requires:
      bins:
        - python3
---

# design-full — 工具说明

> 本文是 `expert-design` 专家包内的工具说明书，不独立出现在技能列表中。设计流程（brief 闸门、设计系统确认、素材、编写、视觉 review、交付）由包内 SKILL.md 与 `workflows/` 编排。

**调用方式**：`design-full <子命令> [参数...]`（wrapper 转发到 `scripts/`，零路径拼接）。`design-full help` 查用法。

| 子命令 | 入 | 出 | 退出码 |
|--------|----|----|--------|
| `design-full init <任务名>` | 任务名（英文短横线式） | `design_assets/YYYY-MM-DD-<任务名>/`（含 `brief.md` 模板、`source/`、`output/`），并确保 `design_assets/references/`、`design_assets/brand/` 存在 | 0 成功 / 1 参数错 |
| `design-full pick "<风格描述>"` | 风格描述（中文关键词即可，如"科技感暗色主题"） | stdout 列出全部可用设计系统 + 按匹配分排序的 1–3 套推荐及理由 | 0 成功 / 1 参数错或索引缺失 |

**注意事项**：

- `init` 按**当前工作目录**建 `design_assets/`，调用时 workdir 必须是 Content Producer workspace 根。
- `init` 幂等：已存在的 `brief.md` 不覆盖（保留已填内容）。
- `pick` 只做匹配与展示，**不写文件**；选定结果由 agent 写入任务目录的 `DESIGN.md`。
- 匹配是关键词打分（keywords / category / name / description），不是语义检索；描述里多放风格词、行业词、色彩词命中率更高。

## 内置设计系统库

每套 8 段规范（Visual Theme / Color / Typography / Components / Layout / Depth / Do's & Don'ts / Responsive），文件在工具目录 `design-systems/<name>.md`，索引 `design-systems/index.json`。

| 设计系统 | 风格关键词 | 适用场景 |
|---------|----------|---------|
| Stripe | 紫色渐变、优雅、金融科技 | SaaS 产品页、支付/金融科技落地页 |
| Vercel | 黑白极简、精密、Geist | 开发者工具、技术产品官网 |
| Linear | 超极简、紫色点缀、精确 | 项目管理、效率工具 |
| Notion | 暖色极简、衬线标题、柔和 | 知识管理、内容平台 |
| Apple | 极致留白、电影级影像 | 消费电子、高端品牌官网 |
| Supabase | 暗色翡翠绿、代码优先 | 数据库/后端服务、开源工具 |
| Shopify | 暗色电影感、霓虹绿 | 电商平台、商业服务 |
| Figma | 多彩活泼、专业、创意 | 创意工具、设计平台 |
| Spotify | 鲜明绿、大胆排版 | 媒体/娱乐平台 |
| Tesla | 极致减法、全屏影像 | 汽车/硬件、极简品牌 |
| Framer | 黑蓝、动效优先 | 网站构建、交互展示 |
| Airbnb | 暖色珊瑚、摄影驱动 | 旅游/生活服务、社区平台 |
| BMW | 巴伐利亚蓝、暗色奢华、金属质感 | 奢侈品牌、高端产品 |
| IBM | 企业蓝、Carbon 系统、数据密集 | 企业级产品、B2B 服务、数据平台 |
| Starbucks | Siren 绿、温暖社区、自然质感 | 生活品牌、餐饮/零售、社区平台 |

## 自定义设计系统

内置库覆盖不到时，基于甲方描述自行构建，输出格式参照内置 DESIGN.md 的标准 8 段结构。

也可从上游仓库 [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) 导入：

1. 访问上述仓库查看完整设计系统列表，或直接访问 `https://getdesign.md/<brand-name>/design-md` 查看特定品牌。
2. 下载为 `design-systems/<name>.md`，补全缺失段落确保 8 段完整。
3. 在 `design-systems/index.json` 添加条目（字段：`id` / `name` / `category` / `keywords` / `description` / `colorPrimary` / `darkMode` / `bestFor` / `file`）。

完成后即可通过 `design-full pick` 搜到。
