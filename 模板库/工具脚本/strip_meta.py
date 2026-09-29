#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
strip_meta.py —— 剥离创作层元信息块，产出对外可读版。

背景：书库每集正文头部带创作层元信息块（本集规则清单 / 涉及人物 / 伏笔编号），
这是规范 E1 要求的流程资产，对内有用，对外发布前必须剥掉。

用法：
    python strip_meta.py <书目根目录> [--outdir 对外版] [--merge]

行为：
    - 删除所有以 '>' 开头的引用行（元信息块）
    - 删除 '---' 分隔线
    - 标题 '# ep01 沉船那夜' → '# 第一章　沉船那夜'
    - 每集单独输出一个 md；加 --merge 另产一个合本
    - 原稿不动，只写输出目录
"""

import os
import re
import sys
import glob
import argparse

CN = "零一二三四五六七八九"


def cn_number(n):
    """1-99 转中文数字"""
    if n < 10:
        return CN[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + CN[n % 10]
    if n % 10 == 0:
        return CN[n // 10] + "十"
    return CN[n // 10] + "十" + CN[n % 10]


def strip_text(text, chapter=None):
    lines = text.split("\n")
    out = []
    for ln in lines:
        s = ln.strip()
        if s.startswith(">"):      # 元信息块
            continue
        if s == "---":             # 分隔线
            continue
        if s.startswith("# ep"):   # 标题改写
            m = re.match(r"#\s*ep(\d+)\s*(.*)", s)
            if m and chapter is None:
                chapter = int(m.group(1))
            title = (m.group(2) if m else s.lstrip("# ").strip())
            if chapter:
                out.append("# 第%s章　%s" % (cn_number(chapter), title))
            else:
                out.append("# %s" % title)
            continue
        out.append(ln)

    # 压掉头部空行与连续 3+ 空行
    res = "\n".join(out)
    res = re.sub(r"\n{3,}", "\n\n", res)
    return res.strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="书目根目录，如 D:/Project/XiaoShuo/荒岛求生")
    ap.add_argument("--outdir", default="对外版", help="输出子目录名")
    ap.add_argument("--merge", action="store_true", help="另产一个合本")
    ap.add_argument("--book", default=None, help="合本标题，默认取目录名")
    args = ap.parse_args()

    root = args.root
    out_root = os.path.join(root, args.outdir)
    os.makedirs(out_root, exist_ok=True)

    files = sorted(glob.glob(os.path.join(root, "ep*.md")))
    if not files:
        print("未找到 ep*.md")
        return 1

    chapters = []
    for fp in files:
        raw = open(fp, encoding="utf-8").read()
        m = re.search(r"#\s*ep(\d+)", raw)
        num = int(m.group(1)) if m else 0
        title_m = re.match(r"#\s*ep\d+\s*(.*)", raw.split("\n")[0])
        title = title_m.group(1).strip() if title_m else os.path.basename(fp)
        clean = strip_text(raw, num)
        dst = os.path.join(out_root, "ep%02d-%s.md" % (num, title))
        open(dst, "w", encoding="utf-8").write(clean)
        chapters.append((num, title, clean))
        print("  剥出 ep%02d %s（%d 字）" % (num, title, len(re.sub(r"\s", "", clean))))

    if args.merge:
        book = args.book or os.path.basename(root.rstrip("/\\"))
        parts = ["# %s\n" % book]
        for num, title, clean in chapters:
            body = clean.split("\n", 1)[1].strip() if "\n" in clean else clean
            parts.append("\n---\n\n# 第%s章　%s\n\n%s\n" % (cn_number(num), title, body))
        merged = "".join(parts)
        dst = os.path.join(out_root, "%s-合本.md" % book)
        open(dst, "w", encoding="utf-8").write(merged)
        total = len(re.sub(r"\s", "", merged))
        print("\n  合本：%s（%d 字 / %.1f 万字）" % (dst, total, total / 10000))

    print("\n完成：%d 集 → %s" % (len(files), out_root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
