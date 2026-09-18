#!/usr/bin/env python3
"""
自动生成 00-总目录.md：
- 扫描 佛家经典/儒家经典/道家经典 下的所有 md
- 解析 front-matter 中的 title/dynasty/author/category
- 按子目录（经/论 等）分组，输出索引表格
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

CATEGORY_TITLES = {
    "佛家经典": "佛家经典",
    "儒家经典": "儒家经典",
    "道家经典": "道家经典",
}

# 子目录显示顺序（数值越小越靠前）；未列出的子目录按字母序排在后
SUBCATEGORY_ORDER = {
    "佛家经典": {
        "经": 1,
        "论": 2,
    },
    "儒家经典": {
        "四书": 1,
        "五经": 2,
        "十三经": 3,
        "心学": 4,
        "蒙学": 5,
    },
    "道家经典": {
        "原典": 1,
        "玄学": 2,
        "道藏经": 3,
        "上清": 4,
        "阴符": 5,
        "内丹": 6,
        "注疏": 7,
        "抱朴": 8,
        "全真": 9,
    },
}


def parse_frontmatter(text: str) -> dict | None:
    """提取文件头部的 YAML front-matter，不依赖 PyYAML 完整解析，简单行解析即可。"""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm_text = text[3:end].strip()
    result = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip().strip('"').strip("'")
        result[k.strip()] = v
    return result


def collect() -> dict:
    """收集所有 .md 文件的元数据，按顶级分类 → 子目录分组。"""
    out: dict[str, dict[str, list]] = {}
    for top in CATEGORY_TITLES:
        top_dir = ROOT / top
        if not top_dir.exists():
            continue
        out[top] = {}
        for md in sorted(top_dir.rglob("*.md")):
            rel = md.relative_to(ROOT)
            try:
                text = md.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            fm = parse_frontmatter(text) or {}
            title = fm.get("title") or md.stem
            dynasty = fm.get("dynasty", "")
            author = fm.get("author", "")
            category = fm.get("category", "")
            sub = rel.parts[1] if len(rel.parts) > 2 else ""
            out[top].setdefault(sub or "(根)", []).append(
                {
                    "title": title,
                    "path": str(rel).replace("\\", "/"),
                    "dynasty": dynasty,
                    "author": author,
                    "category": category,
                }
            )
    return out


def render() -> str:
    data = collect()
    lines = [
        "# 总目录",
        "",
        "> 本目录由 `scripts/gen_toc.py` 自动生成，请勿手工编辑。",
        "> 重新生成： `py scripts/gen_toc.py`",
        "",
    ]

    counts = {}
    for top, subs in data.items():
        counts[top] = sum(len(v) for v in subs.values())
    total = sum(counts.values())
    lines.append(f"## 概览")
    lines.append("")
    lines.append(f"- 收录总数：**{total}** 部")
    for top, c in counts.items():
        lines.append(f"- {CATEGORY_TITLES[top]}：**{c}** 部")
    lines.append("")

    for top, subs in data.items():
        lines.append(f"## {CATEGORY_TITLES[top]}")
        lines.append("")
        # 按 SUBCATEGORY_ORDER 对子目录排序；未列出的子目录按字母序排在后
        order_map = SUBCATEGORY_ORDER.get(top, {})
        for sub in sorted(subs.keys(), key=lambda s: (order_map.get(s, 999), s)):
            lines.append(f"### {sub}")
            lines.append("")
            lines.append("| 书名 | 朝代 | 作者/译者 | 类别 | 路径 |")
            lines.append("|------|------|----------|------|------|")
            for item in sorted(subs[sub], key=lambda x: x["title"]):
                link = f"[{item['title']}]({item['path']})"
                lines.append(
                    f"| {link} | {item['dynasty']} | {item['author']} | {item['category']} | `{item['path']}` |"
                )
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    text = render()
    out = ROOT / "00-总目录.md"
    out.write_text(text, encoding="utf-8")
    print(f"[已写] {out.relative_to(ROOT)}（{len(text)} 字节）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
