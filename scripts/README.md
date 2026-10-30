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

国内客户默认推荐 AtomGit 预构建 tarball，配合 `XIAOBEI_GITHUB_PROXY` 下载第三方 GitHub 资源；客户机无需完整构建 OpenClaw。能正常访问 GitHub 也可使用 `install.sh` / `install.ps1`。两条线路安装产物一致。Windows 中文画面使用系统微软雅黑，不下载 Noto 字体；Docker 保留为需要环境隔离的可选渠道。

### Ubuntu / Debian 系统依赖

`install.sh` 和 `install-atomgit.sh` 在下载与解压前检查 `curl`、`tar`、`zstd`、`ca-certificates`、`python3`、`python3-pip`。存在缺项时先执行 `apt-get update`，再仅安装缺少的包；依赖齐全则跳过 apt。普通用户通过 `sudo` 安装系统包，程序与运行数据仍归该用户；root 直接运行时直接调用 apt。权限不足、apt 失败或安装后 Python/pip 仍不可用时提前退出，升级路线此时尚未停止已有 Gateway。其他平台保留原有系统依赖准备方式。

安装脚本自带的 Node/pnpm 和预构建 OpenClaw 不要求预装系统 Node、Git 或完整编译工具。Python 库仍由脚本使用可用的 Python/pip 安装，并优先选择已有 pip 的解释器。

下面的一行安装命令使用 `curl` 获取脚本，因此极简系统若连 curl 或 CA 证书也没有，需要先准备这两项，或先通过浏览器取得脚本再本地执行：

```bash
sudo apt update
sudo apt install -y curl ca-certificates
```

### 安装命令

```bash
# macOS / Linux（GitHub 线路）
bash -c "$(curl -fsSL https://raw.githubusercontent.com/TeamWiseFlow/xiaobei/master/scripts/install.sh)"
# macOS / Linux（国内推荐；脚本与主程序从 AtomGit 下载）
export XIAOBEI_GITHUB_PROXY="https://ghfast.top/"
bash -c "$(curl -fsSL https://raw.atomgit.com/wiseflow/xiaobei/raw/master/scripts/install-atomgit.sh)"
```

```powershell
# Windows（PowerShell，需 Git Bash 或 WSL；GitHub 线路）
irm https://raw.githubusercontent.com/TeamWiseFlow/xiaobei/master/scripts/install.ps1 | iex
# Windows（国内推荐；脚本与主程序从 AtomGit 下载）
$env:XIAOBEI_GITHUB_PROXY="https://ghfast.top/"
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
| `--skip-browser` | `XIAOBEI_SKIP_BROWSER=1` | 跳过 Camoufox Firefox 与共享 Chromium 下载（冒烟 / CI） |
| `--no-prompt` | `XIAOBEI_NO_PROMPT=1` | 关闭交互提示（CI / 自动化，隐含 `--skip-bind`） |
| `--root <dir>` | `XIAOBEI_HOME=<dir>` | 程序目录覆盖（默认 `~/xiaobei`） |
| — | `XIAOBEI_TAG=<tag>` | 指定版本 tag（默认拉最新 release；sh 也认 `XIAOBEI_TAG` env） |
| — | `XIAOBEI_TARBALL=<path>` | 本地已下好的 tarball 路径，跳过下载（sh 也认此 env） |
| `--verbose` | — | 打印 debug 输出（仅 sh） |

环境变量：`XIAOBEI_REPO`（仅 GitHub 线路认，atomgit 线路硬编码 `wiseflow/xiaobei`）、`XIAOBEI_TAG`（指定版本）、`XIAOBEI_TARBALL`（本地已下好的 tarball 路径，跳过下载）、`XIAOBEI_HOME`（程序目录覆盖）、`OPENCLAW_HOME`（运行数据目录覆盖）。

### GitHub 下载代理

`XIAOBEI_GITHUB_PROXY` 是可选的 HTTPS URL 前缀，例如 `https://ghfast.top/`。不设置或设为空时保持原有下载线路；启用后将 GitHub 下载地址改写成 `https://ghfast.top/https://github.com/...`。可以更换代理站点，不能包含账号密码、查询参数或 fragment。

| 入口 | 启用后的行为 |
|------|------|
| 四个 install 脚本 | GitHub release/raw/API 地址加前缀；AtomGit API、tarball/CDN 保持原线路 |
| Camoufox、GeoIP、指纹模型 | 使用统一前缀；版本锁、缓存与 SHA-256 校验保留 |
| Matrix 原生库 | 通过依赖支持的 `MATRIX_SDK_CRYPTO_DOWNLOADS_BASE_URL` 下载 |
| 源码 update/apply、npm/pnpm 的 GitHub Git 依赖 | 通过进程级 Git 配置改写 HTTPS/SSH 地址；不修改 remote 或全局 Git 配置 |
| npm/pnpm、Node headers | 未自定义时分别使用 npmmirror 包源和 Node headers 镜像 |
| Playwright Chromium | 未自定义时使用 `https://registry.npmmirror.com/-/binary/playwright`，下载超时 120 秒 |

共享资源安装入口 `install-browser.mjs`、`install-skill-deps.mjs` 与 deck-render 安装器也识别该变量。现有 `PLAYWRIGHT_DOWNLOAD_HOST`、各浏览器专用下载地址、`MATRIX_SDK_CRYPTO_DOWNLOADS_BASE_URL` 等镜像设置继续生效。安装器将配置传给子进程，不写入 Gateway 配置或系统环境文件。新终端里首装、重跑或升级时需重新设置变量。

部分代理（包含本次检查的 ghfast）不支持 GitHub API。推荐使用 AtomGit 查询最新版本；若选择 GitHub 安装线路，应额外指定 `XIAOBEI_TAG`。代理模式查询失败时安装器会提示处理，不会通过 gh CLI 自动绕回 GitHub 直连。最外层下载 GitHub 安装脚本的 `curl` / `irm` 发生在脚本运行前，需要调用者自行加前缀；上面的 AtomGit 命令无需处理这个问题。

该功能需要使用包含 `browser/scripts/download-network.mjs` 的新 tarball；仅更新 bootstrap 脚本不能让旧发行包获得资源代理能力，启用变量时遇到旧包会明确报错。

此变量不是通用 HTTP/HTTPS 代理。Mozilla 的 uBlock、apt/brew/winget 等系统包管理器、ONNX 可选 NuGet 下载等仍按各自配置访问，不对这些地址机械添加 GitHub 前缀；完整国内网络安装还需逐项验证这些来源。无 CUDA 的 CPU 云电脑可另设 `ONNXRUNTIME_NODE_INSTALL_CUDA=skip`，此开关不自动改变 GPU 安装选项。

#### 浏览器资源下载缓存

弱网下下载浏览器压缩包，可先用支持续传的下载器保存为 `<缓存目录>/<assets.lock.json 中的平台 asset.name>`，设置 `XIAOBEI_BROWSER_DOWNLOADS=<缓存目录>`，再单独运行 `node browser/scripts/install-assets.mjs`。资源安装器会先核对 SHA-256，再使用缓存，不需要重跑 OpenClaw 构建；缓存文件不能只改名或跳过校验。该缓存入口也适用于 uBlock 和 GeoIP，指纹模型使用 SDK 自身的安装目录。

Camoufox、uBlock 和 GeoIP 的内置资源下载默认包含首次最多尝试 5 次。连接中断、HTTP 408/429/5xx 会分别等待 3、6、12、24 秒后重试；同一次安装中优先用 Range 续传，服务端不支持时从头重下。每 30 秒显示下载进度，连续 2 分钟没有新数据才超时，没有固定的总下载时限。HTTP 403/404、磁盘写入错误和 SHA-256 校验失败会立即报错。指纹模型沿用 SDK 自带的重试，并打印请求次数及错误原因。

当前锁定的 Camoufox 156.0.1-beta.36 Linux x64 包经 Range 探测为 1,294,875,941 字节（约 1.29 GB），支持断点续传。安装结束或重试耗尽后临时文件仍会清理；需要跨次安装保留部分下载时，应使用上面的独立缓存和续传下载器。资源安装器末尾出现 `Camoufox ... ready at ...` 才表示资源安装完成。

源码用户使用同一变量，例如：

```bash
export XIAOBEI_GITHUB_PROXY="https://ghfast.top/"
bash scripts/update.sh --atomgit
```

执行流程：

1. 检测 OS + arch → 选 tarball asset（linux-x64 / mac-arm64 / mac-x64 / win-x64）
2. 解析最新 release tag（GitHub 线路走 `api.github.com`，回退 gh CLI；atomgit 线路走 `api.atomgit.com/api/v5`；`XIAOBEI_TAG` 直接指定）
3. 下载预构建 tarball → 解压到 `~/xiaobei/`（程序目录）
4. `pnpm install --prod --frozen-lockfile`（用自带的 portable Node + pnpm，在 `openclaw/` 下）
5. `pip install --user`（skills 的 Python 依赖）
6. awada 本地插件 deps（`awada/` 下 `npm install --omit=dev` 装 ws+zod）
7. `install-browser.mjs`：先安装 `browser/package.json` 锁定的 Playwright，再调用 `install-playwright.mjs` 预装配套 Chromium headless shell，并准备 Camoufox 固定资产。驱动仅在 `browser/node_modules`，唯一 Chromium 缓存为 `browser/.browsers`；`--skip-assets` 同时跳过 Chromium 下载。已有浏览器资源会复用。
8. `install-deck-render.sh`（Windows 为 `.ps1`）：安装或校验 FFmpeg/FFprobe、锁定 HyperFrames/GSAP、实例共享 Playwright/Chromium 与中文字体（Linux/macOS 为 Noto Sans CJK SC，Windows 为系统微软雅黑）；重跑会复用已有依赖。
9. `openclaw plugins install @tencent-weixin/openclaw-weixin@<pin> --pin`（微信插件，走 npmmirror）
10. 首装：放 `config-templates/openclaw.json` → `~/.openclaw/` + 预填微信 binding + `setup-crew.sh` + 交互收 `AWK_API_KEY` + `openclaw daemon install` + restart
11. 首装末尾：自动出微信绑定二维码（已绑过则跳过），手机扫码确认即用
12. 升级：只刷 `daemon.env` 路径 + restart gateway，不碰运行数据

> 目录职责：`~/xiaobei/` = 程序（引擎 + 模板 + 脚本 + 工具 + wrapper）；`~/.openclaw/` = 运行数据（openclaw.json + daemon.env + workspaces + logs）。升级只换 `~/xiaobei/`，用户数据不动。

GitHub PR CI 检查 Linux/macOS 的便携 pnpm 离线启动、补丁应用、依赖安装、引擎构建、CLI 入口与技能依赖重复安装。发布 workflow 在上传 tarball 前对 Linux 包执行首装和重跑升级，检查用户配置、工作区文件、登录态文件和 API key 保留；冒烟跳过浏览器下载与微信扫码，服务托管及真实平台登录仍需实际环境验证。

`prepare-portable-pnpm.mjs` 从仓根 `package.json` 的 `packageManager` 读取 pnpm 版本及 SHA-512，下载并校验 launcher 和四个平台对应的 `@pnpm/exe.*` 原生包，保留 `tools/pnpm/bin/pnpm.mjs` 安装入口。原生文件按启动器支持的 `pnpm-native` / `pnpm-native.exe` 路径放在 pnpm 根目录，与 `dist/` 同级，确保生命周期脚本能找到内置的 node-gyp。pnpm 12 的 npm 包不再含 `dist/pnpm.mjs`，只复制 launcher 会在首次使用时额外下载原生文件，因此 tarball 必须携带目标平台的原生文件；引擎的 `node_modules` 仍由用户安装时重建。PR CI 使用 `--platform host` 准备本机包，禁止启动器联网下载，验证版本和 node-gyp 脚本；Linux/macOS 还会在隔离项目中直接调用 `install.sh`、`install-atomgit.sh` 的真实依赖安装函数，检查完整命令参数。重试次数通过 pnpm 12 支持的进程环境变量 `PNPM_CONFIG_FETCH_RETRIES=5` 设置，不使用其 CLI 不支持的 `--fetch-retries`；请求超时和并发参数保持不变。发布使用默认 `--platform all` 准备四个平台，再用 portable Node 验证 Linux 入口。包结构、校验或安装参数失败会在 OpenClaw clone/build 前报错。

---

## update.sh

**已 `git clone` 仓做开发的用户的升级路线**。fetch + rebuild，校验并补齐变化的依赖，不卸 daemon、不碰运行数据。普通用户用 `install.sh` 即可，不需要这个脚本。

更新脚本在 `apply-addons.sh` 后调用同一个 deck-render 安装脚本，校验 npm 包、浏览器与字体。tarball 安装脚本的 `--skip-browser`（PowerShell 为 `XIAOBEI_SKIP_BROWSER=1`）会跳过 Chromium 下载与 Camoufox Firefox 下载，供 CI 冒烟使用；正常安装与更新会预装。

Windows 缺少 FFmpeg/FFprobe 时安装器通过 winget 安装 `Gyan.FFmpeg`。Windows 版 deck-render 检查系统微软雅黑的 Light、Regular、Bold 字体文件，不联网下载 Noto；若系统缺少微软雅黑，应先启用 Windows 简体中文字体功能。

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
| 小白首装（macOS/Linux，国内 atomgit） | 先 `export XIAOBEI_GITHUB_PROXY="https://ghfast.top/"`，再运行上面的 AtomGit 安装命令 |
| 小白首装（Windows，GitHub） | **以管理员身份打开 PowerShell**，然后 `irm https://raw.githubusercontent.com/TeamWiseFlow/xiaobei/master/scripts/install.ps1 \| iex` |
| 小白首装（Windows，国内 atomgit） | **以管理员身份打开 PowerShell**，先设置 `$env:XIAOBEI_GITHUB_PROXY="https://ghfast.top/"`，再运行上面的 AtomGit 安装命令 |
| 老用户升级 | 重跑对应线路的 install 脚本（保留 `~/.openclaw` 运行数据） |
| 已 git clone 的开发者升级 | `./scripts/update.sh` |
| 修改了 patch 后测试 | `./scripts/apply-addons.sh` |
| 修改了 crew markdown 后同步 | `./scripts/setup-crew.sh` |
| 开发调试（前台运行） | `cd openclaw && pnpm build && cd .. && ./scripts/dev.sh gateway` |
