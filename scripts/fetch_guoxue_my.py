#!/usr/bin/env python3
"""
从 https://www.guoxue.my 抓取经典正文。

用法：
  py scripts/fetch_guoxue_my.py <output_dir> <book_id> <book_title> <chapter_id> <chapter_title>
  或通过 --config 传入 JSON

每个章节页面有：
  <h1>章题</h1>
  <正文段落，每段之间有空行>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parent.parent


def fetch(url: str) -> str:
    """带 UA 的 GET 请求，返回 utf-8 文本。"""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ConfucianismBot/1.0)"})
    with urlopen(req, timeout=30) as r:
        raw = r.read()
    return raw.decode("utf-8", errors="replace")


def parse_chapter(html: str, original_only: bool = True) -> tuple[str, str]:
    """提取 (章节标题, 正文)。

    guoxue.my 的格式有两种：
    1. <div class="wenzbody"> <p>原文<br><span style="color:#af9100;">译文</span></p> ... </div>
    2. <div class="wenzbody"> 原文<br>译文<br>... </div> （如尔雅）
    """
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    title = m.group(1).strip() if m else ""
    body_match = re.search(r'<div class="wenzbody">(.*?)</div>\s*<div', html, re.DOTALL | re.IGNORECASE)
    if not body_match:
        body_match = re.search(r'<div class="wenzbody">(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    body = body_match.group(1) if body_match else ""

    if original_only:
        # 去掉 <span>...</span> 译文
        body = re.sub(r"<span[^>]*>.*?</span>", "", body, flags=re.DOTALL)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)

    # 优先按 <p>...</p> 切，没有则按 \n\n 切
    if "<p>" in body or "<p " in body:
        paras = re.split(r"</?p[^>]*>", body)
    else:
        # 按 <br> 替换后的换行切
        paras = body.split("\n")

    cleaned = []
    for p in paras:
        text = re.sub(r"<[^>]+>", "", p).strip()
        text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        if "上一章" in text or "下一章" in text:
            continue
        if text.startswith("Powered by"):
            continue
        if text.startswith("章节目录"):
            continue
        if text:
            cleaned.append(text)
    return title, "\n\n".join(cleaned)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="JSON 配置文件路径")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base = cfg["base_url"]
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    original_only = cfg.get("original_only", True)

    parts = []
    for part in cfg["parts"]:
        part_title = part["title"]
        parts.append(f"## {part_title}\n")
        for ch in part["chapters"]:
            url_id = ch["id"]
            ch_title = ch["title"]
            url = f"{base}/{url_id}.html"
            print(f"[fetch] {url}", file=sys.stderr)
            try:
                html = fetch(url)
                title, body = parse_chapter(html, original_only=original_only)
            except Exception as e:
                print(f"  [错误] {url}: {e}", file=sys.stderr)
                continue
            if not body:
                print(f"  [警告] {url}: 正文为空", file=sys.stderr)
            parts.append(f"### {title or ch_title}\n")
            parts.append(body)
            parts.append("")  # 段间空行
        parts.append("")  # 部分之间空行

    # front-matter
    fm_lines = [
        "---",
        f'title: "{cfg["title"]}"',
        f'dynasty: "{cfg["dynasty"]}"',
        f'author: "{cfg["author"]}"',
        f'category: "{cfg["category"]}"',
        f'source: "{cfg["source"]}"',
        f'public_domain: {str(cfg.get("public_domain", True)).lower()}',
        "---",
        "",
        f"# {cfg['title']}",
        "",
        cfg.get("preface", ""),
        "",
    ]
    full = "\n".join(fm_lines) + "\n" + "\n".join(parts)
    out_path = out_dir / f"{cfg['title']}.md"
    out_path.write_text(full, encoding="utf-8")
    print(f"\n[已写] {out_path.relative_to(ROOT)}（{len(full)} 字节）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
