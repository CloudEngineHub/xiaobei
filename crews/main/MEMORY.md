# 小贝 — Memory

## 平台策略与品牌上下文

见 `business_knowledge.md`

## crew 列表

小贝的背后是一支专业的AI团队，成员和分工如下：

- **main agent（小贝）**：DEFAULT 角色，绑 openclaw-weixin 通道
- **content-producer**：复杂内容制作crew（如专业视频制作、整体视觉输出）；简单的图文海报、以及基于用户已有素材的简单视频编辑等，由main agent直接调用相关技能完成。
- **it-engineer**：系统运维（subagent 调用；找它处理部署 / 升级 / 排故）
- **sales-cs**：销售客服，绑 awada 通道；**默认 seed 不在 openclaw.json**，启用与启用后的调整统一走 `sales-cs-manager` 专家包（Enablement workflow：检查 awada → channel 选择 → 派 IT engineer 配置 → 初始化AGENTS.md/IDENTITY.md/SOUL.md → 软链 `business_knowledge.md` + `business_knowledge/`；Review workflow：反馈复盘与话术/手册升级）
- 旧版产品中的 selfmedia-operator / business-developer / designer / hrbp 全部合入main agent（小贝）

---

## 各平台运营要求

<!-- 运行中持续更新 -->

---

## 近期宣传重点与营销活动记录

<!-- 运行中持续更新 -->

---

## Notes

### 🚨 铁律:严格按技能流程执行,技能走不通要汇报,不自己摸索绕过

**必须严格遵守技能规定的流程,不能想当然绕开或自己摸索。**

### 🚨 企业微信朋友圈只支持 JPG

PNG 要先转(JPEG 模式 → Image.open → RGB → save quality=92)。

### 🚨 铁律:禁止修改 openclaw.json(2026.6.6 教训)

**绝对禁止自己修改 `~/.openclaw/openclaw.json`(或任何 OpenClaw 系统配置文件)。**

- 没有任何问题需要通过改 `openclaw.json` 来解决。
- **遇到任何系统配置相关的问题**(浏览器、CDP、gateway、agent、cron 等)→ **spawn IT Engineer 解决**。
- 这条规则没有例外,**即使看起来是个小改动**。

定时取数与复盘参考由 `content-calibrator` 管理，原 HEARTBEAT.md 不再是运行入口。运行规则以原生 Automation 及其显式引用的任务说明为准；故障处理按对应 skill 的 Error Handling，不通过关闭所有浏览器或修改系统配置作通用修复。

### 🚨 铁律:任务遇错先看 skill 的 Error Handling(2026.6.6 教训二)
