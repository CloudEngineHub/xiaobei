# scripts/ 脚本说明

## 脚本总览

| 脚本 | 用途 | 平台 | 拉 tarball | pnpm install --prod | camoufox/weixin/awada | 微信扫码绑定 | gateway daemon |
|------|------|------|:---:|:---:|:---:|:---:|:---:|
| `install.sh` | 首装 / 升级（tarball 路线，GitHub 线路） | macOS + Linux | ✅ | ✅ | ✅ | ✅ | ✅ |
| `install-atomgit.sh` | 首装 / 升级（tarball 路线，atomgit 国内线路） | macOS + Linux | ✅ | ✅ | ✅ | ✅ | ✅ |
| `install.ps1` | 首装 / 升级（tarball 路线，GitHub 线路） | Windows（需 Git Bash/WSL） | ✅ | ✅ | ✅ | ✅ | ✅ |
| `install-atomgit.ps1` | 首装 / 升级（tarball 路线，atomgit 国内线路） | Windows（需 Git Bash/WSL） | ✅ | ✅ | ✅ | ✅ | ✅ |
| `update.sh` | 已 git clone 开发用户的升级 | macOS + Linux | — | — | ✅ | — | ✅ |
| `apply-addons.sh` | 本地测试 addon 改动 | macOS + Linux | — | ✅ | ✅ | — | ✅ |
| `dev.sh` | 开发模式（前台 gateway） | macOS + Linux | — | ✅ | — | — | — |
| `setup-crew.sh` | 仅同步 crew markdown | 跨平台（bash） | — | — | — | — | — |

---

## install.sh / install-atomgit.sh / install.ps1 / install-atomgit.ps1

**一键首装 / 升级**（预构建 tarball 路线）。新用户首装和老用户升级都跑这一个脚本，重跑即升级、保留运行数据。

按网络环境选一条命令即可：能正常访问 GitHub 走 GitHub 线路（`install.sh` / `install.ps1`）；国内网络走 atomgit 线路（`install-atomgit.sh` / `install-atomgit.ps1`，全程不经 GitHub）。两条线路安装产物完全一致，只是下载源不同。

```bash
# macOS / Linux（GitHub 线路）
bash -c "$(curl -fsSL https://raw.githubusercontent.com/TeamWiseFlow/xiaobei/master/scripts/install.sh)"
# macOS / Linux（atomgit 线路，国内；tarball 走 atomgit.com → GitCode CDN，全程国内直连，脚本也从 raw.atomgit.com 拉取）
bash -c "$(curl -fsSL https://raw.atomgit.com/wiseflow/xiaobei/raw/master/scripts/install-atomgit.sh)"
```

```powershell
# Windows（PowerShell，需 Git Bash 或 WSL；GitHub 线路）
irm https://raw.githubusercontent.com/TeamWiseFlow/xiaobei/master/scripts/install.ps1 | iex
# Windows（atomgit 线路，国内；脚本和 tarball 全程走 atomgit，不经 GitHub）
irm https://raw.atomgit.com/wiseflow/xiaobei/raw/master/scripts/install-atomgit.ps1 | iex
```

> **Windows 用户请以管理员身份运行 PowerShell 再安装**（右键 PowerShell → "以管理员身份运行"）。
> 原因：安装过程中的 `setup-crew.sh` 会用 `ln -s` 把 crew skills 软链到 workspace，创建 NTFS 符号链接需要管理员权限（或开启 Windows 开发者模式）。
> - **管理员模式**：软链创建成功，仓库里改 skill 即生效，无需重跑安装。**推荐。**
> - **普通用户（不开开发者模式）**：软链失败时自动回退到拷贝（`cp -rf`），功能完全可用，但仓库 skill 改动不会自动同步到 workspace，需要重跑 `setup-crew.sh --force`。
> - **普通用户 + 开启开发者模式**：`设置 → 隐私和安全性 → 开发者选项 → 开发人员模式` 打开，即可创建软链，无需管理员。

常用参数（四个 install 脚本行为开关同构；sh 走 `--flag`，ps1 走 `$env:XIAOBEI_FLAG=1`）：

| 参数（sh） | env（ps1） | 作用 |
|------|------|------|
| `--force` | `XIAOBEI_FORCE=1` | 强覆盖已有运行数据（`~/.openclaw`）；默认已装机器重跑只更新 program，不碰运行数据 |
| `--skip-bind` | `XIAOBEI_SKIP_BIND=1` | 跳过末尾微信扫码绑定（CI / 自动化） |
| `--skip-browser` | `XIAOBEI_SKIP_BROWSER=1` | 跳过 camoufox-cli 浏览器二进制安装（冒烟 / CI，省 ~557MB Firefox 下载） |
| `--no-prompt` | `XIAOBEI_NO_PROMPT=1` | 关闭交互提示（CI / 自动化，隐含 `--skip-bind`） |
| `--root <dir>` | `XIAOBEI_HOME=<dir>` | 程序目录覆盖（默认 `~/xiaobei`） |
| — | `XIAOBEI_TAG=<tag>` | 指定版本 tag（默认拉最新 release；sh 也认 `XIAOBEI_TAG` env） |
| — | `XIAOBEI_TARBALL=<path>` | 本地已下好的 tarball 路径，跳过下载（sh 也认此 env） |
| `--verbose` | — | 打印 debug 输出（仅 sh） |

环境变量：`XIAOBEI_REPO`（仅 GitHub 线路认，atomgit 线路硬编码 `wiseflow/xiaobei`）、`XIAOBEI_TAG`（指定版本）、`XIAOBEI_TARBALL`（本地已下好的 tarball 路径，跳过下载）、`XIAOBEI_HOME`（程序目录覆盖）、`OPENCLAW_HOME`（运行数据目录覆盖）。

执行流程：

1. 检测 OS + arch → 选 tarball asset（linux-x64 / mac-arm64 / mac-x64 / win-x64）
2. 解析最新 release tag（GitHub 线路走 `api.github.com`，回退 gh CLI；atomgit 线路走 `api.atomgit.com/api/v5`；`XIAOBEI_TAG` 直接指定）
3. 下载预构建 tarball → 解压到 `~/xiaobei/`（程序目录）
4. `pnpm install --prod --frozen-lockfile`（用自带的 portable Node + pnpm，在 `openclaw/` 下）
5. `pip install --user`（skills 的 Python 依赖）
6. awada 本地插件 deps（`awada/` 下 `npm install --omit=dev` 装 ws+zod）
7. `camoufox-cli install`（下 Firefox 反指纹浏览器，约 557MB，仅首装）
8. `openclaw plugins install @tencent-weixin/openclaw-weixin@<pin> --pin`（微信插件，走 npmmirror）
9. 首装：放 `config-templates/openclaw.json` → `~/.openclaw/` + 预填微信 binding + `setup-crew.sh` + 交互收 `AWK_API_KEY` + `openclaw daemon install` + restart
10. 首装末尾：自动出微信绑定二维码（已绑过则跳过），手机扫码确认即用
11. 升级：只刷 `daemon.env` 路径 + restart gateway，不碰运行数据

> 目录职责：`~/xiaobei/` = 程序（引擎 + 模板 + 脚本 + 工具 + wrapper）；`~/.openclaw/` = 运行数据（openclaw.json + daemon.env + workspaces + logs）。升级只换 `~/xiaobei/`，用户数据不动。

---

## update.sh

**已 `git clone` 仓做开发的用户的升级路线**。fetch + rebuild，不重装依赖、不卸 daemon、不碰运行数据。普通用户用 `install.sh` 即可，不需要这个脚本。

```bash
./scripts/update.sh              # fetch + apply addons + build + restart
./scripts/update.sh --skip-crew  # 跳过 crew workspace 同步
```

---

## apply-addons.sh

**应用 addon 改动后一步到位**。用于新增/修改了 patch、skill 或 crew 模板后的本地测试。不拉远程代码，不升级 openclaw 版本——直接用本地已有源码。

```bash
./scripts/apply-addons.sh              # 应用 addons + build + restart gateway
./scripts/apply-addons.sh --skip-crew  # 跳过 crew workspace 同步
./scripts/apply-addons.sh --no-build   # 不执行 pnpm build（调用方自行处理）
./scripts/apply-addons.sh --no-restart # 不重启 gateway service
./scripts/apply-addons.sh --force      # 强制覆盖已有 workspace 文件
```

执行流程：

1. 恢复 `openclaw/` 到干净状态（`git reset --hard`）
2. 同步 `config-templates/` 中的配置项到运行时 `openclaw.json`
3. 安装全局 skills（`skills/` → `openclaw/skills/`）
4. 依次加载各 addon：overrides → patches → skills → crew 模板
5. `pnpm install`（仅有 overrides/patches 时）
6. `setup-crew.sh`（同步 crew workspace，可 `--skip-crew` 跳过）
7. `pnpm build`（编译 dist，可 `--no-build` 跳过）
8. `systemctl restart`（重启 gateway，可 `--no-restart` 跳过）

---

## dev.sh

**开发模式前台运行**。自动 apply addons，但**不 build**——需要用户自行 `cd openclaw && pnpm build`。

```bash
cd openclaw && pnpm build && cd ..   # 首次或修改源码后手动 build
./scripts/dev.sh gateway             # 前台启动 gateway
./scripts/dev.sh cli config set ...  # 运行 openclaw CLI 命令
```

---

## setup-crew.sh

**仅同步 crew workspace 的 markdown 文件**。不碰源码，不 build，不重启。适合只更新了 crew 模板内容（SOUL.md、AGENTS.md 等）的场景。

```bash
./scripts/setup-crew.sh          # 幂等同步（不覆盖已有文件）
./scripts/setup-crew.sh --force  # 强制覆盖（含 MEMORY.md 等个性化文件）
```

---

## 典型场景速查

| 场景 | 命令 |
|------|------|
| 小白首装（macOS/Linux，GitHub） | `bash -c "$(curl -fsSL https://raw.githubusercontent.com/TeamWiseFlow/xiaobei/master/scripts/install.sh)"` |
| 小白首装（macOS/Linux，国内 atomgit） | `bash -c "$(curl -fsSL https://raw.atomgit.com/wiseflow/xiaobei/raw/master/scripts/install-atomgit.sh)"` |
| 小白首装（Windows，GitHub） | **以管理员身份打开 PowerShell**，然后 `irm https://raw.githubusercontent.com/TeamWiseFlow/xiaobei/master/scripts/install.ps1 \| iex` |
| 小白首装（Windows，国内 atomgit） | **以管理员身份打开 PowerShell**，然后 `irm https://raw.atomgit.com/wiseflow/xiaobei/raw/master/scripts/install-atomgit.ps1 \| iex` |
| 老用户升级 | 重跑对应线路的 install 脚本（保留 `~/.openclaw` 运行数据） |
| 已 git clone 的开发者升级 | `./scripts/update.sh` |
| 修改了 patch 后测试 | `./scripts/apply-addons.sh` |
| 修改了 crew markdown 后同步 | `./scripts/setup-crew.sh` |
| 开发调试（前台运行） | `cd openclaw && pnpm build && cd .. && ./scripts/dev.sh gateway` |
