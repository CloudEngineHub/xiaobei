#!/usr/bin/env python3
"""Maintain generated AGENTS.md guidance without rewriting user notes or placeholders."""

from pathlib import Path
import sys


HEADING = "## 多行内容与真实换行"
GUIDE = r"""## 多行内容与真实换行

有些模型会把本应是**真实换行**的地方写成字面量 `\n`（反斜杠和 n 两个字符）。这会让普通文档、字幕、配置、消息正文和代码都挤成一行；问题不限于 Python。

- 写多行内容时，直接用文件写入工具传入实际分行的正文；用 shell 写文件时，heredoc 的正文也要实际分行。不要把多行内容先拼成带字面量 `\n` 的一行再原样写入。
- 写完后读回文件，核对预期的行数和段落。若本应多行的内容挤在一行，并出现本该用于断行的字面量 `\n`，先修正文件，再继续后续步骤；不要只凭“写入成功”判断。
- ✅ 目标文件实际内容：
  ```text
  第一行
  第二行
  ```
  ❌ 错误的单行内容：`第一行\n第二行`
- 多行 Python 也遵守同一规则：先写有真实换行的 `.py` 文件，再运行 `python3 /path/to/script.py`；不要用带字面量 `\n` 的 `python3 -c` 拼脚本。
- **保留有意的转义**：JSON 字符串、代码字符串、正则表达式等场景中，`\n` 可能是合法的转义写法；工具调用日志也可能转义展示换行。以最终文件或接收端的实际内容为准，不要对整份文件盲目全局替换。"""


def updated_text(content: str) -> str:
    if HEADING in content:
        return content
    separator = "" if content.endswith("\n\n") else "\n" if content.endswith("\n") else "\n\n"
    return content + separator + GUIDE + "\n"


def main() -> None:
    action, filename, *args = sys.argv[1:]
    path = Path(filename)
    original = path.read_bytes()
    content = original.decode("utf-8")
    if action == "newline" and not args:
        revised = updated_text(content)
    elif action == "append" and len(args) == 1:
        # Render only the new block. Literal @@WS@@ in user notes must stay untouched.
        revised = content + sys.stdin.buffer.read().decode("utf-8").replace("@@WS@@", args[0])
    else:
        raise SystemExit("Usage: workspace-guides.py newline FILE | append FILE WORKSPACE")
    if revised != content:
        if path.read_bytes() != original:
            raise SystemExit("Workspace file changed while preparing guidance; retry")
        path.write_bytes(revised.encode("utf-8"))


if __name__ == "__main__":
    main()
