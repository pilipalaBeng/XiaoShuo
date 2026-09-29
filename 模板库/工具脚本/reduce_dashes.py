#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破折号精简 reduce_dashes.py v1.0

依据《小说写作通用规则.md》§一 A3 与《文风执行细则》§1.2：破折号仅用于
  ① 语句中断/转折（对白被打断）② 规则的“真实版”补充说明；
禁止用于“解说式拖长”。

转换规则（保守、可解释）：
  `——` **保留**当且仅当它紧跟 `”` 或 `【`，或位于行尾（＝被打断/被截断/引出面板条文）；
  其余一律替换为 `，`（即把“解说式拖长”降级为正常停顿）。
不改变任何其他文字。

用法:
    python reduce_dashes.py <项目目录|书库根> [--dry-run] [--books a,b]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import novel_lint_core as C  # noqa: E402

SKIP = {"模板库", "_总控", ".workbuddy", ".git"}
KEEP_NEXT = ("\u201d", "【")      # ” 或 【 → 保留


def reduce_body(body: str):
    out = []
    kept = conv = 0
    for line in body.split("\n"):
        res = []
        i = 0
        while i < len(line):
            if line.startswith(C.DASH, i):
                nxt = line[i + 2: i + 3]
                if nxt == "" or nxt in KEEP_NEXT:
                    res.append(C.DASH)
                    kept += 1
                else:
                    res.append("，")
                    conv += 1
                i += 2
                continue
            res.append(line[i])
            i += 1
        out.append("".join(res))
    return "\n".join(out), kept, conv


def process(path: Path, dry: bool):
    raw = path.read_text(encoding="utf-8", errors="replace")
    header, body = C.split_front_matter(raw)
    before = C.dash_count(body)
    new_body, kept, conv = reduce_body(body)
    after = C.dash_count(new_body)
    if not dry and before != after:
        path.write_text(header + new_body, encoding="utf-8")
    return before, after, kept, conv


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="破折号精简")
    ap.add_argument("target")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--books", default=None)
    ap.add_argument("--limit", type=int, default=5, help="目标上限（默认 5）")
    a = ap.parse_args()

    root = Path(a.target).resolve()
    want = set(a.books.split(",")) if a.books else None
    books = []
    if C.episode_files(root):
        books = [root]
    else:
        for d in sorted(root.iterdir()):
            if d.is_dir() and d.name not in SKIP and not d.name.startswith(".") and C.episode_files(d):
                if want is None or d.name in want:
                    books.append(d)

    grand_before = grand_after = 0
    still = []
    for b in books:
        tb = ta = 0
        changed = 0
        for p in C.episode_files(b):
            before, after, kept, conv = process(p, a.dry_run)
            tb += before
            ta += after
            if after != before:
                changed += 1
            if after > a.limit:
                still.append((b.name, p.name, after, kept))
        grand_before += tb
        grand_after += ta
        if tb or ta:
            print(f"{b.name:<7} 破折号 {tb:>4} → {ta:>4}（改动 {changed} 集）"
                  f"{'  [dry-run]' if a.dry_run else ''}")
    print(f"\n合计 {grand_before} → {grand_after}")
    if still:
        print(f"\n仍超上限 {a.limit} 的集（{len(still)}）——这些是「被打断/被截断」型破折号，属合法用法，需人工判断是否再精简：")
        for bk, f, n, kept in sorted(still, key=lambda t: -t[2])[:25]:
            print(f"  {bk}/{f}  剩 {n}（其中保留型 {kept}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
