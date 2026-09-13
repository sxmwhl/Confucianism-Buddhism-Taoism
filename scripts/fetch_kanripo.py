#!/usr/bin/env python3
"""
从 Kanripo GitHub 抓取繁体古籍 → 转换为简体 → 生成 markdown 文件。

用法：
  py scripts/fetch_kanripo.py --config scripts/data/liji.json

配置 JSON 见 scripts/data/*.json。

处理流程：
1. 下载每个 *_NNN.txt 文件
2. 跳过文件头的 org-mode 元数据（# -*- / #+ / #+PROPERTY:）
3. 去除 <pb:...> 分页标记和 ¶ 行内断句符
4. 去除 # src: / # dating: 注释
5. 用 OpenCC t2s 转换为简体
6. 重新按卷（juan）分段，章节小标题单独成段
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    import opencc
except ImportError:
    print("[错误] 需要 opencc-python-reimplemented。请先：py -m pip install opencc-python-reimplemented", file=sys.stderr)
    sys.exit(1)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Confucianism-Buddhism-Taoism/1.0 (public domain text)"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return raw.decode("utf-8", errors="replace")


def clean_text(content: str) -> str:
    """清理 Kanripo mandoku 文本：去除 org-mode 元数据、注释、分页标记、换行符。"""
    # 先处理分页标记和注释
    content = re.sub(r"<pb:[^>]*>", "", content)
    content = re.sub(r"^#\s*-\*-\s*mode:.*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^#\+[A-Z]+:.*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^# src:.*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^# dating:.*$", "", content, flags=re.MULTILINE)
    return content


def strip_pipel(line: str) -> str:
    """去除 ¶ 标记和空白。"""
    return line.replace("¶", "").strip()


def detect_juan_number(filename: str) -> int:
    m = re.search(r"_(\d+)\.txt$", filename)
    return int(m.group(1)) if m else 0


def detect_title_from_header(content: str) -> str:
    """从 org-mode 头部 #+TITLE: 读取原始繁体书名。"""
    m = re.search(r"^\#\+TITLE:\s*(.+)$", content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def extract_chapter_heading(line: str) -> tuple[str, str] | None:
    """识别章节小标题（如 `** 1 曲禮上`），返回 (level, title)；否则 None。"""
    m = re.match(r"^\*+\s+(.+)$", line)
    if m:
        # Kanripo 用 `** N 标题` 表示三级标题，数字前是篇号
        title = m.group(1).strip()
        return title
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    repo = cfg["repo"]              # e.g. kanripo/KR1d0052
    base_url = cfg["base_url"]      # e.g. https://raw.githubusercontent.com/kanripo/KR1d0052/master
    title = cfg["title"]
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 获取文件列表
    contents_url = f"https://api.github.com/repos/{repo}/contents/"
    try:
        raw = fetch(contents_url)
        file_list = json.loads(raw)
    except Exception as e:
        print(f"[错误] 无法读取 {contents_url}: {e}", file=sys.stderr)
        return 1

    txt_files = sorted(
        [f["name"] for f in file_list if f["name"].endswith(".txt") and f["name"] != "Readme.org"],
        key=lambda n: int(re.search(r"_(\d+)\.txt$", n).group(1)) if re.search(r"_(\d+)\.txt$", n) else 0,
    )
    print(f"[信息] 共 {len(txt_files)} 个文本文件", file=sys.stderr)

    converter = opencc.OpenCC("t2s")

    all_parts = []  # [(part_title, [chapter_text])]

    # 2) 并发下载所有文件（带重试）
    def fetch_and_clean(fname: str):
        url = f"{base_url}/{fname}"
        for attempt in range(3):
            try:
                content = fetch(url)
                return fname, content, None
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                else:
                    return fname, None, str(e)

    print(f"[fetch] 并发下载 {len(txt_files)} 个文件...", file=sys.stderr)
    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_and_clean, fn): fn for fn in txt_files}
        for fut in as_completed(futures):
            fname, content, err = fut.result()
            if err:
                print(f"  [错误] {fname}: {err}", file=sys.stderr)
                continue
            results[fname] = content
            print(f"  [下载] {fname} ({len(content)} bytes)", file=sys.stderr)

    # 3) 按卷顺序处理
    for fname in txt_files:
        content = results.get(fname)
        if not content:
            continue
        print(f"[process] {fname}", file=sys.stderr)

        cleaned = clean_text(content)
        # 合并 ¶ 标记：把 <pb:...>¶ 这种结构都去掉 ¶
        # 把 ¶ 替换为换行符以便分段
        cleaned = cleaned.replace("¶", "\n")
        cleaned_simp = converter.convert(cleaned)

        # 按章节标题分段
        chapters = []
        current = []
        for line in cleaned_simp.splitlines():
            line = line.rstrip()
            if not line:
                # 连续空行只保留一个作为段间分隔
                if current and current[-1] != "":
                    current.append("")
                continue
            heading = extract_chapter_heading(line)
            # 兼容：左传/公羊/穀梁等无 ** 标题的格式
            if not heading:
                # 兼容半角/全角括号
                # 1) 「春秋X卷Y（起...）」- 左传卷标
                m = re.match(
                    r"^[\s　]*(春秋.*?卷[一二三四五六七八九十百千]+(?:[-][一二三四五六七八九十]+)?)"
                    r"(?:\s*[（(].*?[)）])?\s*$",
                    line,
                )
                if m:
                    heading = m.group(1).strip()
                else:
                    # 2) 「春秋公羊卷第X」/「春秋X传卷第X」 - 卷尾标识
                    m = re.match(
                        r"^[\s　]*(春秋.*?(?:公羊|穀梁|左).*?卷第[一二三四五六七八九十百]+)\s*$",
                        line,
                    )
                    if m:
                        heading = m.group(1).strip()
                    else:
                        # 3) 「春秋公羊经传解诂隐公第一」- 隐公/桓公/庄公等
                        m = re.match(
                            r"^[\s　]*(春秋.*?[隐桓庄闵僖文宣成襄昭定哀]+公(?:[一二三四五六七八九十百]+)?)"
                            r"(?:第[一二三四五六七八九十百]+)?\s*$",
                            line,
                        )
                        if m:
                            heading = m.group(1).strip()
            if heading:
                if current:
                    chapters.append("\n".join(current).strip())
                current = [f"### {heading}"]
            else:
                current.append(line)
        if current:
            # 移除尾部空行
            while current and current[-1] == "":
                current.pop()
            chapters.append("\n".join(current).strip())

        # 提取每个章节内部所有非空段落
        cleaned_chapters = []
        for ch in chapters:
            paragraphs = [p.strip() for p in ch.split("\n") if p.strip()]
            if paragraphs:
                cleaned_chapters.append(paragraphs)
        if cleaned_chapters:
            all_parts.append(cleaned_chapters)

    # 3) 输出 Markdown
    fm = [
        "---",
        f'title: "{cfg["title"]}"',
        f'dynasty: "{cfg["dynasty"]}"',
        f'author: "{cfg["author"]}"',
        f'category: "{cfg["category"]}"',
        f'source: "{cfg["source"]}"',
        "public_domain: true",
        "---",
        "",
        f"# {cfg['title']}",
        "",
        cfg.get("preface", ""),
        "",
    ]
    body_lines = []
    for part_chapters in all_parts:
        if len(all_parts) > 1:
            body_lines.append("## 卷")
            body_lines.append("")
        for ch_paras in part_chapters:
            title_line = ch_paras[0]
            body_lines.append(title_line)
            body_lines.append("")
            body_lines.extend(ch_paras[1:])
            body_lines.append("")

    full = "\n".join(fm) + "\n" + "\n".join(body_lines)
    out_path = out_dir / f"{cfg['title']}.md"
    out_path.write_text(full, encoding="utf-8")
    print(f"\n[已写] {out_path.relative_to(ROOT)}（{len(full)} 字节）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
