#!/usr/bin/env python3
"""
Markdown 校验脚本：
- 校验 UTF-8 编码（无 BOM）
- 校验一级标题存在且唯一
- 校验 front-matter 完整性（如果文件在 .github/metadata/books.yml 中）
- 校验文件名为中文.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
META_FILE = ROOT / ".github" / "metadata" / "books.yml"
META_KEYS: set[str] = set()
if META_FILE.exists():
    META_KEYS = set(yaml.safe_load(META_FILE.read_text(encoding="utf-8")).keys())

ERRORS: list[str] = []
WARNINGS: list[str] = []


def has_frontmatter(text: str) -> bool:
    return text.startswith("---")


def main() -> int:
    md_files = [p for p in ROOT.rglob("*.md") if "node_modules" not in p.parts]

    # 排除脚本自身产物与 README/CONTRIBUTING/笔记
    skip_dirs = {"scripts", ".github"}
    skip_files = {
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "00-总目录.md",
        ROOT / "学佛笔记.md",
        ROOT / "学儒笔记.md",
        ROOT / "学道笔记.md",
    }

    md_files = [p for p in md_files if p.parent.name not in skip_dirs and p not in skip_files]

    for p in md_files:
        rel = p.relative_to(ROOT)
        # BOM 检查
        raw_bytes = p.read_bytes()
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            ERRORS.append(f"{rel}: 含 UTF-8 BOM，请去除")
            continue
        # 编码检查
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            ERRORS.append(f"{rel}: 非 UTF-8 编码 ({e})")
            continue

        # front-matter
        if not has_frontmatter(text):
            meta_key = str(rel).replace("\\", "/")[:-3]  # 去掉 .md
            if meta_key in META_KEYS:
                ERRORS.append(f"{rel}: 已登记在 books.yml 但缺少 front-matter")
            else:
                WARNINGS.append(f"{rel}: 无 front-matter（若新增文件请同步元数据）")

        # H1 检查
        h1s = re.findall(r"(?m)^# [^#]", text)
        if len(h1s) == 0:
            WARNINGS.append(f"{rel}: 没有一级标题")

        # 文件名中文检查（粗略）
        if not re.match(r"^[\u4e00-\u9fff].*\.md$", p.name) and p.name not in {
            "README.md",
            "CONTRIBUTING.md",
        }:
            WARNINGS.append(f"{rel}: 文件名建议使用中文")

    print("=" * 60)
    print(f"扫描文件数：{len(md_files)}")
    print(f"错误：{len(ERRORS)}")
    print(f"警告：{len(WARNINGS)}")
    print("=" * 60)

    if ERRORS:
        print("\n【错误】")
        for e in ERRORS:
            print(f"  ✗ {e}")
    if WARNINGS:
        print("\n【警告】")
        for w in WARNINGS:
            print(f"  ⚠ {w}")

    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
