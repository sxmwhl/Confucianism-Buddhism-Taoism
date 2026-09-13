#!/usr/bin/env python3
"""
为 Markdown 文件添加 YAML front-matter（仅公版原文原则）。
- 已存在 front-matter 的文件跳过
- 路径以 YAML 元数据键为基准（POSIX 风格）
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[错误] 需要 PyYAML。请先运行: py -m pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
META_FILE = ROOT / ".github" / "metadata" / "books.yml"


def render_frontmatter(meta: dict) -> str:
    """生成 YAML front-matter（注意保持中文可读性）。"""
    lines = ["---"]
    for key in ("title", "dynasty", "author", "category", "source", "notes"):
        if meta.get(key):
            val = str(meta[key]).replace("|", "\\|").replace("\n", " ")
            lines.append(f'{key}: "{val}"')
    if meta.get("public_domain") is not None:
        lines.append(f"public_domain: {str(meta['public_domain']).lower()}")
    lines.append("---")
    lines.append("")  # front-matter 末尾空行
    return "\n".join(lines)


def has_frontmatter(text: str) -> bool:
    return text.startswith("---")


def add_one(rel_path: str, meta: dict) -> str:
    rel = rel_path
    if not rel.endswith(".md"):
        rel = rel + ".md"
    fp = ROOT / rel
    if not fp.exists():
        return f"[跳过] {rel} (文件不存在)"
    raw = fp.read_text(encoding="utf-8")
    if has_frontmatter(raw):
        return f"[已有] {rel}"
    fm = render_frontmatter(meta)
    # 保留原内容，前面插入 front-matter
    new_text = fm + raw
    fp.write_text(new_text, encoding="utf-8")
    return f"[已加] {rel}", new_text[:200]


def main() -> int:
    data = yaml.safe_load(META_FILE.read_text(encoding="utf-8"))
    applied = skipped = missing = 0
    for rel, meta in data.items():
        rel_posix = rel.replace("\\", "/")
        result = add_one(rel_posix, meta)
        if isinstance(result, tuple):
            result, preview = result
        else:
            preview = ""
        if "[已加]" in result:
            applied += 1
            print(result, file=sys.stderr)
        elif "[已有]" in result:
            skipped += 1
            print(result, file=sys.stderr)
        else:
            missing += 1
            print(result, file=sys.stderr)
    summary = f"\n汇总: 新增 {applied}，已有 {skipped}，缺失 {missing}"
    print(summary, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
