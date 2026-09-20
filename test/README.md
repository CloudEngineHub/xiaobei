# 回归测试

测试及夹具统一放在本目录，按组件分组。测试使用 mock、临时工作区或本地浏览器页面，不执行真实发布。

从仓根运行：

```bash
# Python 技能测试；DOM 测试需要已安装 camoufox-cli 和浏览器
python3 -m unittest discover -s test/skills -p 'test_*.py'
python3 test/skills/check_fill_browser.py

# Node.js 原生测试（使用支持 TypeScript strip-types 的 Node.js）
node --experimental-strip-types --test test/skills/test-upstream-catchup.ts
node test/test-douyin-metrics.mjs

# camoufox-cli 与 Awada；先安装 patches/camoufox-cli 的开发依赖
# Awada accounts 测试需要仓内 openclaw 已构建 dist/plugin-sdk
patches/camoufox-cli/node_modules/.bin/vitest run --config test/vitest.config.mts
```

`patches/camoufox-cli` 中的 `npm test` / `npm run test:watch` 也指向这份统一配置。

`skills/`、`crews/`、`awada/src/` 不放测试脚本。`patches/` 中用于修改上游测试的补丁材料保留在补丁包内。
