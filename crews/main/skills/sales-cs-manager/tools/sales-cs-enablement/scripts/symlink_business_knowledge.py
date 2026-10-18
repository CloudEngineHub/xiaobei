#!/usr/bin/env python3
"""Maintain one shared business_knowledge directory and migrate the legacy document."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

DOCUMENT = "business_knowledge.md"
DIRECTORY = "business_knowledge"
CANONICAL = f"{DIRECTORY}/{DOCUMENT}"
WORKSPACE_DOCS = ("AGENTS.md", "SOUL.md", "MEMORY.md", "BOOTSTRAP.md", "USER.md", "OFB_ENV.md")


def rewrite_references(text: str) -> str:
    text = text.replace(
        "`business_knowledge.md` 同级有一个**支撑文件夹** `business_knowledge/`，存放业务知识的**引用型材料**",
        "`business_knowledge/` 同时存放正文与**引用型材料**",
    ).replace(
        "正文写 `.md`，素材放文件夹，在 `.md` 里用相对路径引用（如 `见 business_knowledge/pricing-2026.png`）",
        "正文位于 `business_knowledge/business_knowledge.md`，正文内相对链接以该目录为基准（如 `./pricing-2026.png`）",
    ).replace(
        "其他crew的workspace通过软链同时访问这两者",
        "其他 crew 的 workspace 只通过 `business_knowledge/` 目录软链共享正文和材料",
    )
    text = re.sub(
        r"^> Workspace下`business_knowledge\.md`为软链接，注意使用 `find` 命令查询时要加 `-L`[ \t]*$",
        "共享的 `business_knowledge/` 目录由 main 维护，正文是目录内的普通文件。",
        text, flags=re.MULTILINE,
    )
    text = text.replace("软链 `business_knowledge.md` + `business_knowledge/`", "软链 `business_knowledge/` 目录")
    return re.sub(r"(?<!business_knowledge/)business_knowledge\.md", CANONICAL, text)


def relocated_markdown(text: str) -> str:
    """Keep relative Markdown destinations pointing at the same files after the move."""
    def replace(match: re.Match[str]) -> str:
        target = match.group(0)
        angled = target.startswith("<")
        value = target[1:-1] if angled else target
        parts = urlsplit(value)
        if not parts.path or parts.scheme or parts.netloc or parts.path.startswith("/"):
            return target
        rel = posixpath.normpath(parts.path)
        moved = DOCUMENT if rel == DOCUMENT else posixpath.relpath(rel, DIRECTORY)
        value = urlunsplit(("", "", moved, parts.query, parts.fragment))
        return f"<{value}>" if angled else value
    return re.sub(r"(?<=\]\()(<[^>\n]+>|[^\s)]+)", replace, text)


def rewrite_shared_readme(text: str) -> str:
    text = text.replace("# business_knowledge/ — 业务知识支撑材料", "# business_knowledge/ — 业务知识与支撑材料")
    text = text.replace(
        "> 这是 `business_knowledge.md`（**单文件**，位于上级目录）的**支撑文件夹**。\n"
        "> 业务知识**正文**写在 `../business_knowledge.md` 里；本文件夹只放**引用型材料**：",
        "> 业务知识正文是本目录内的普通文件 `business_knowledge.md`；本目录同时存放正文与**引用型材料**：",
    ).replace("- ❌ 不放：业务知识正文（正文进 `business_knowledge.md`）\n", "")
    text = text.replace("../business_knowledge.md", DOCUMENT).replace("见 business_knowledge/", "见 ./")
    text = text.replace("sales-cs workspace 通过软链访问本文件夹（与 `business_knowledge.md` 一同软链）。", "其他 crew 只通过 `business_knowledge/` 目录软链共享正文和材料。")
    if "├── business_knowledge.md" not in text:
        text = text.replace("├── README.md", "├── business_knowledge.md   # 业务知识正文\n├── README.md")
    return text


def migrate(main: Path, workspaces: list[Path], repo_main: Path, backup_base: Path) -> dict:
    main = main.absolute()
    workspaces = list(dict.fromkeys(ws.absolute() for ws in workspaces if ws.resolve() != main.resolve()))
    shared = main / DIRECTORY
    document = shared / DOCUMENT
    legacy = main / DOCUMENT
    legacy_bytes = legacy.read_bytes() if legacy.is_file() else None
    migrated_bytes = relocated_markdown(legacy_bytes.decode("utf-8")).encode("utf-8") if legacy_bytes is not None else None
    if legacy.is_symlink() and legacy_bytes is None:
        raise ValueError(f"旧业务知识软链不可读，保留原状: {legacy}")
    if legacy.exists() and legacy_bytes is None:
        raise ValueError(f"旧业务知识不是普通文件，保留原状: {legacy}")
    if document.is_symlink() or (document.exists() and not document.is_file()):
        raise ValueError(f"正文必须是目录内的普通文件: {document}")
    if document.exists() and legacy_bytes is not None and document.read_bytes() not in (legacy_bytes, migrated_bytes):
        raise ValueError(f"新旧业务知识内容冲突，保留两份文件: {legacy}, {document}")
    known_targets = {legacy.resolve(), document.resolve()}
    old_links = []
    for ws in workspaces:
        target = ws / DIRECTORY
        if target.exists() and not target.is_symlink():
            raise ValueError(f"共享目录已存在且不是软链，拒绝覆盖: {target}")
        old = ws / DOCUMENT
        if old.is_symlink() and old.resolve() in known_targets:
            old_links.append(old)
        elif old.exists() or old.is_symlink():
            raise ValueError(f"旧正文不是本次共享软链，拒绝移除: {old}")

    backup_dir = None
    def backup(path: Path, workspace: Path) -> None:
        nonlocal backup_dir
        if backup_dir is None:
            backup_base.mkdir(parents=True, exist_ok=True)
            backup_dir = Path(tempfile.mkdtemp(prefix="business-knowledge-" + datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=backup_base))
        target = backup_dir / workspace.name / path.relative_to(workspace)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() and not target.is_symlink():
            shutil.copy2(path, target, follow_symlinks=False)

    def update(path: Path, revised: bytes, workspace: Path, expected: bytes | None = None) -> bool:
        original = path.read_bytes()
        if expected is not None and original != expected:
            raise ValueError(f"文件在准备迁移期间被修改，停止: {path}")
        if original == revised:
            return False
        backup(path, workspace)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".knowledge-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(revised)
        try:
            shutil.copystat(path, temporary)
            if path.read_bytes() != original:
                raise ValueError(f"文件在迁移期间被修改，保留备份并停止: {path}")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return True

    shared.mkdir(parents=True, exist_ok=True)
    if legacy_bytes is not None:
        backup(legacy, main)
        if legacy.read_bytes() != legacy_bytes:
            raise ValueError(f"业务知识在迁移期间被修改，停止: {legacy}")
        if not document.exists():
            if legacy.is_symlink():
                shutil.copy2(legacy, document)
            else:
                legacy.replace(document)
        if document.read_bytes() == legacy_bytes:
            update(document, migrated_bytes, main, expected=legacy_bytes)
        legacy.unlink(missing_ok=True)
    elif not document.exists():
        seed = repo_main / DIRECTORY / DOCUMENT
        if seed.is_file():
            shutil.copy2(seed, document)
        else:
            document.write_text("# 业务知识（business_knowledge）\n\n（待补充）\n", encoding="utf-8")
    readme = shared / "README.md"
    if not readme.exists() and (repo_main / DIRECTORY / "README.md").is_file():
        shutil.copy2(repo_main / DIRECTORY / "README.md", readme)

    source = shared.resolve()
    linked = []
    for ws in workspaces:
        ws.mkdir(parents=True, exist_ok=True)
        target = ws / DIRECTORY
        if not target.is_symlink() or target.resolve() != source:
            if target.is_symlink():
                backup(target, ws)
                target.unlink()
            target.symlink_to(source, target_is_directory=True)
            linked.append(str(target))
    for old in old_links:
        backup(old, old.parent)
        old.unlink()
    updated = []
    for ws in [main, *workspaces]:
        for name in WORKSPACE_DOCS:
            path = ws / name
            if path.is_file() and not path.is_symlink():
                text = path.read_bytes().decode("utf-8")
                if update(path, rewrite_references(text).encode("utf-8"), ws, expected=text.encode("utf-8")):
                    updated.append(str(path))
    if readme.is_file() and not readme.is_symlink():
        text = readme.read_bytes().decode("utf-8")
        if update(readme, rewrite_shared_readme(text).encode("utf-8"), main, expected=text.encode("utf-8")):
            updated.append(str(readme))
    return {"document": str(document), "migrated": legacy_bytes is not None, "linked": linked,
            "removedFileLinks": [str(p) for p in old_links], "updatedReferences": updated,
            "backup": str(backup_dir) if backup_dir else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", action="append", type=Path, help="Target workspace; repeat for multiple crews")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    source = Path(os.environ.get("MAIN_WORKSPACE", str(Path.home() / ".openclaw/workspace-main")))
    repo_main = Path(os.environ.get("REPO_MAIN", str(Path(__file__).resolve().parents[5])))
    targets = args.workspace or [Path(os.environ.get("SALES_CS_WORKSPACE", str(Path.home() / ".openclaw/workspace-sales-cs")))]
    try:
        result = migrate(source, targets, repo_main, args.backup_dir or source.parent / "backups")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
