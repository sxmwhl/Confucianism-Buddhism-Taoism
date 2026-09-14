#!/usr/bin/env python3
"""
从 guoxue.my 抓取简体经典文本（修订版 v3）。

支持两种索引模式：
1. 单页索引（如 /liji/liji1.html）—— 章节目录在一个页面
2. 多页索引（如 /zuozhuan/index.html）—— 章节目录跨多个二级标题（隐公/桓公/...）

用法：
  py scripts/fetch_guoxue_my.py --config scripts/data/liji_v3.json

配置 JSON 字段：
  title, dynasty, author, category, source
  output_dir: 输出目录
  base_url: 例如 https://www.guoxue.my/liji/
  index_url: 章节目录页 URL
  index_mode: "single" 或 "multi"
    single: 单页索引，所有 li>a 链接都是章节
    multi: 多页索引，每 ## 子标题（隐公/桓公/...）下有 li>a 章节
  strip_translation: bool，是否去除现代白话翻译
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


def fetch(url: str, retries: int = 3) -> str:
    headers = {
        "User-Agent": "Confucianism-Buddhism-Taoism/1.0 (public domain text archive)",
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            return raw.decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise


def extract_chapter_links_single(index_html: str) -> list[tuple[str, str]]:
    """从单页索引提取 (chapter_id, chapter_title)。"""
    links = re.findall(
        r'<li>\s*<a[^>]*href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>\s*</li>',
        index_html,
    )
    return [(href, title.strip()) for href, title in links if href.endswith(".html")]


def extract_chapter_links_multi(index_html: str) -> list[tuple[str, str, str]]:
    """从多页索引提取 (chapter_id, chapter_title, parent_title)。
    guoxue.my 实际格式：
      <h2><a href="zuozhuan1.html">《左传》隐公</a></h2>
      <ul>
        <li><a href="1649774907.html">隐公元年</a></li>
        ...
      </ul>
    """
    out = []
    # 按 <h2> 分块
    parts = re.split(r"<h2[^>]*>", index_html)
    for part in parts[1:]:  # 跳过第一个 <h2> 之前的内容
        # 提取 h2 文本和链接
        m_h2 = re.match(r"\s*(.*?)</h2>", part, re.DOTALL)
        if not m_h2:
            continue
        h2_raw = m_h2.group(1)
        # h2 内可能含 <a href="...">标题</a>
        h2_link_m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', h2_raw, re.DOTALL)
        if h2_link_m:
            parent_title = re.sub(r"<[^>]+>", "", h2_link_m.group(2)).strip()
        else:
            parent_title = re.sub(r"<[^>]+>", "", h2_raw).strip()
        parent_title = parent_title.lstrip("《》").strip()
        # 截取 <h2> 之后到下一个 <h*> 之前
        after = part[m_h2.end():]
        # 找下一个 h2/h3/h4 标签
        next_h = re.search(r"<h[1-6][^>]*>", after)
        if next_h:
            after = after[:next_h.start()]
        # 找所有 li > a 章节链接
        for li_m in re.finditer(r"<li>\s*(.*?)</li>", after, re.DOTALL):
            li_content = li_m.group(1)
            for a_m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', li_content, re.DOTALL):
                href = a_m.group(1).strip()
                title = re.sub(r"<[^>]+>", "", a_m.group(2)).strip()
                if href.endswith(".html") and title:
                    out.append((href, title, parent_title))
    return out


def parse_chapter(html: str, strip_translation: bool = False) -> tuple[str, str]:
    """解析章节内容页面。返回 (章节标题, 章节正文)。"""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    title = m.group(1).strip() if m else ""

    # 正文体在 <div class="wenzbody"> ... </div>
    body_match = re.search(
        r'<div\s+class="wenzbody"[^>]*>(.*?)</div>\s*<div',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not body_match:
        body_match = re.search(
            r'<div\s+class="wenzbody"[^>]*>(.*?)</body>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
    body = body_match.group(1) if body_match else ""

    if strip_translation:
        # 去除 guoxue.my 的现代白话翻译
        # 格式 1：<span style="color:#af9100;">...</span>
        body = re.sub(
            r'<span[^>]*style="[^"]*color:\s*#af9100[^"]*"[^>]*>.*?</span>',
            "",
            body,
            flags=re.DOTALL,
        )
        # 格式 2：【翻译】... 直到下一个段落
        body = re.sub(
            r"【翻译】.*?(?=<h\d|</div>|<p|$)",
            "",
            body,
            flags=re.DOTALL,
        )

    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"</?p[^>]*>", "\n\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<[^>]+>", "", body)
    body = (body.replace("&nbsp;", " ")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&amp;", "&")
                .replace("&#39;", "'")
                .replace("&quot;", '"'))

    paras = []
    current = []
    for line in body.split("\n"):
        line = line.rstrip()
        if not line.strip():
            if current:
                paras.append("".join(current))
                current = []
            continue
        current.append(line.strip())
    if current:
        paras.append("".join(current))

    return title, "\n\n".join(paras).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base_url = cfg["base_url"].rstrip("/")
    output_dir = ROOT / cfg["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    strip_translation = cfg.get("strip_translation", False)
    index_url = cfg["index_url"]

    print(f"[信息] 抓取 {cfg['title']} 章节列表...", file=sys.stderr)
    index_html = fetch(index_url)

    index_mode = cfg.get("index_mode", "single")
    if index_mode == "multi":
        items = extract_chapter_links_multi(index_html)
    else:
        items = extract_chapter_links_single(index_html)

    print(f"[信息] 共 {len(items)} 个章节", file=sys.stderr)

    def fetch_chapter(item):
        if len(item) == 3:
            link_id, link_title, _ = item
        else:
            link_id, link_title = item
        url = f"{base_url}/{link_id}"
        try:
            html = fetch(url)
            _, body = parse_chapter(html, strip_translation=strip_translation)
            return link_id, link_title, body, None
        except Exception as e:
            return link_id, link_title, "", str(e)

    chapters = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_chapter, item): item for item in items}
        for fut in as_completed(futures):
            lid, lt, body, err = fut.result()
            if err:
                print(f"  [错误] {lid}: {err}", file=sys.stderr)
                continue
            if len(item := fut.result()) == 3:
                chapters.append((lid, lt, body))
            else:
                # 找对应 item 的 parent
                for it in items:
                    if it[0] == lid and it[1] == lt:
                        if len(it) == 3:
                            chapters.append((lid, lt, body))
                        else:
                            chapters.append((lid, lt, body))
                        break
            print(f"  [下载] {lid} ({len(body)} chars)", file=sys.stderr)

    # 按原始顺序排序
    order_map = {it[0]: i for i, it in enumerate(items)}
    def sort_key(item):
        return order_map.get(item[0], 9999)
    chapters.sort(key=sort_key)

    # 输出 Markdown
    fm_lines = [
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
    prev_parent = None
    for chapter in chapters:
        if len(chapter) == 3:
            link_id, link_title, content = chapter
            parent = None
        else:
            link_id, link_title, parent, content = chapter
        if not content:
            continue
        if parent and parent != prev_parent:
            body_lines.append(f"## {parent}")
            body_lines.append("")
            prev_parent = parent
        body_lines.append(f"### {link_title}")
        body_lines.append("")
        body_lines.append(content)
        body_lines.append("")

    full = "\n".join(fm_lines) + "\n" + "\n".join(body_lines)
    out_path = output_dir / f"{cfg['title']}.md"
    out_path.write_text(full, encoding="utf-8")
    print(f"\n[已写] {out_path.relative_to(ROOT)}（{len(full)} 字节，{len(chapters)} 章节）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
