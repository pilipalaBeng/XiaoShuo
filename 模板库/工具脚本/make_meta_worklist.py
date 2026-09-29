#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成元信息清理工单 make_meta_worklist.py v1.0

扫描全库正文，列出所有**创作层标记**（集号/伏笔编号/规则编号/幕级用语/进度用语），
输出 `_总控/04-元信息清理工单.md`，供逐条清理。判据与 lint_episode.py 的 B1/B2 一致。

用法:
    python make_meta_worklist.py <书库根> [--out 路径]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import novel_lint_core as C  # noqa: E402

SKIP = {"模板库", "_总控", ".workbuddy", ".git"}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    root = Path(a.root).resolve()
    per_book = defaultdict(list)
    type_counter = Counter()
    total = 0
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name in SKIP or d.name.startswith("."):
            continue
        for p in C.episode_files(d):
            _, body = C.body_of(p)
            lines = body.split("\n")
            fail, _ = C.meta_hits(body)
            for ln, label, _t in fail:
                full = lines[ln - 1].strip() if ln - 1 < len(lines) else ""
                per_book[d.name].append((p.name, ln, label, full))
                type_counter[label] += 1
                total += 1

    out = ["# 元信息清理工单（正文内创作层标记）", "",
           f"> 生成时间：{_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}　｜　工具：`模板库/工具脚本/make_meta_worklist.py`",
           "> 判据与 `lint_episode.py` 的 B1（元信息入正文）/ B2（编号入对话）一致。",
           "> **行号是「正文相对行号」**（已剥离文首元信息块），与文件实际行号差 3–6 行，定位请以内容为准。",
           "> 清理原则：**只删/只换标记本身，不动剧情、不动其余文字**。", "",
           f"命中总数：**{total}**", "",
           "| 类型 | 数量 |", "|---|---|"]
    for k, v in type_counter.most_common():
        out.append(f"| {k} | {v} |")
    out += ["", "| 书 | 命中数 |", "|---|---|"]
    for k, v in sorted(per_book.items(), key=lambda t: -len(t[1])):
        out.append(f"| {k} | {len(v)} |")
    out += ["", "---", "", "## 逐条工单", ""]
    for book, items in sorted(per_book.items(), key=lambda t: -len(t[1])):
        out += [f"### {book}（{len(items)} 处）", ""]
        for f, ln, lab, full in items:
            out += [f"- **{f}** L{ln} `[{lab}]`", f"  - 原文：{full}"]
        out.append("")

    dst = Path(a.out) if a.out else root / "_总控" / "04-元信息清理工单.md"
    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] 工单已写入 {dst}")
    print(f"命中总数 {total}")
    for k, v in sorted(per_book.items(), key=lambda t: -len(t[1])):
        print(f"  {k:<7} {len(v)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
