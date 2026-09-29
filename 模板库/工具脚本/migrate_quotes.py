#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标点体例迁移 migrate_quotes.py v1.0

依据 D2-2026-09-23-01：全库正文标点体例统一为中文弯引号 “ ”。
把「」直角引号、ASCII 直引号（含生成事故遗留的连排 "" ）统一转为 “ ”；
引号内引用（ASCII 单引号对）转为 ‘ ’。

只改标点，**不动任何文字内容**；改完必须跑 lint_episode.py 验证。

用法:
    python migrate_quotes.py <书库根>                      # 全库迁移
    python migrate_quotes.py <书库根> --dry-run            # 只统计，不写入
    python migrate_quotes.py <书库根> --books 荒野规则,萌宠  # 限量
    python migrate_quotes.py <书库根> --include-docs       # 连设定/台账文档一起转（默认只转 ep*.md）
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import novel_lint_core as C  # noqa: E402

SKIP = {"模板库", "_总控", ".workbuddy", ".git"}


def convert_text(text: str, collapse: bool):
    """返回 (新文本, 统计)。collapse=True 时先把连排 "" 折叠为一对。

    是否折叠必须逐文件判断：本库同时存在两种相反情况——
      ① 生成事故的损坏引号：每一处引号都被写成了两个（""对话""）；
      ② 合法的相邻对白：。"A。""B。" 里那对 "" 是"上句收尾+下句起头"，不能折叠。
    折错了会把两句对白缝成一句（实测会造成新的单边引号）。
    """
    st = {"doubled": 0, "corner": 0, "ascii": 0, "ascii_single": 0}

    # 1) 连排 ASCII 双引号（仅损坏文件）
    if collapse:
        text, n = re.subn(r'"{2,}', '"', text)
        st["doubled"] = n

    # 2) 直角引号 → 中文弯引号（1:1，安全）
    st["corner"] = text.count("\u300c") + text.count("\u300d")
    text = text.replace("\u300c", "\u201c").replace("\u300d", "\u201d")

    # 3) 剩余 ASCII 双引号：全文交替为 “ ”
    #    用文件级配对（不是行级）——中文对白可能跨行，行级配对会把跨行的成对引号切成两个单边引号。
    res, open_next = [], True
    for ch in text:
        if ch == '"':
            res.append("\u201c" if open_next else "\u201d")
            open_next = not open_next
            st["ascii"] += 1
        else:
            res.append(ch)
    text = "".join(res)

    # 4) ASCII 单引号（引号内引用）：全文交替为 ‘ ’
    res, open_next = [], True
    for ch in text:
        if ch == "'":
            res.append("\u2018" if open_next else "\u2019")
            open_next = not open_next
            st["ascii_single"] += 1
        else:
            res.append(ch)
    text = "".join(res)

    return text, st


def malformed_count(text: str) -> int:
    """畸变引号计数：空引号对（“”）、同向连排（““ / ””）。

    这是识别"损坏引号文件"的关键指标——损坏文本不折叠时会得到 “”X“” 这类空引号对。
    """
    return (text.count("\u201c\u201d") + text.count("\u201c\u201c")
            + text.count("\u201d\u201d"))


def convert_best(text: str):
    """两种策略都试，取"配平最好 → 畸变最少 → 残留最少 → 破坏最小"的那个。"""
    out = []
    for collapse in (False, True):
        new, st = convert_text(text, collapse)
        bad = len(C.quote_balance_scan(new))
        mal = malformed_count(new)
        residue = new.count('"') + new.count("\u300c") + new.count("\u300d")
        out.append((bad, mal, residue, 1 if collapse else 0, new, st))
    out.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    bad, mal, _, collapsed, new, st = out[0]
    st["collapse_used"] = bool(collapsed)
    st["unpaired_after"] = bad
    st["malformed_after"] = mal
    return new, st


def migrate_book(book: Path, dry: bool, include_docs: bool):
    files = C.episode_files(book)
    if include_docs:
        files = files + [p for p in sorted(book.glob("*.md"))
                         if p not in files and p.name != "机械门禁与校验规范.md"]
    rec = {"书": book.name, "文件数": len(files), "改动文件": 0, "doubled": 0,
           "corner": 0, "ascii": 0, "ascii_single": 0, "chars_before": 0,
           "chars_after": 0, "unpaired_before": 0, "unpaired_after": 0, "samples": []}
    for p in files:
        raw = p.read_text(encoding="utf-8", errors="replace")
        new, st = convert_best(raw)
        rec["chars_before"] += len(raw)
        rec["unpaired_before"] += len(C.quote_census(raw)["unpaired_lines"])
        if new == raw:
            rec["chars_after"] += len(new)
            rec["unpaired_after"] += len(C.quote_census(new)["unpaired_lines"])
            continue
        rec["改动文件"] += 1
        for k in ("doubled", "corner", "ascii", "ascii_single"):
            rec[k] += st[k]
        rec["chars_after"] += len(new)
        rec["unpaired_after"] += len(C.quote_census(new)["unpaired_lines"])
        if len(rec["samples"]) < 3:
            for a, b in zip(raw.split("\n"), new.split("\n")):
                if a != b:
                    rec["samples"].append((p.name, a.strip()[:64], b.strip()[:64]))
                    break
        if not dry:
            p.write_text(new, encoding="utf-8")
    return rec


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="标点体例迁移（→ 中文弯引号）")
    ap.add_argument("root")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--books", default=None, help="逗号分隔的书名，默认全部")
    ap.add_argument("--include-docs", action="store_true", help="连设定/台账文档一起转")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    want = set(a.books.split(",")) if a.books else None
    books = [d for d in sorted(root.iterdir())
             if d.is_dir() and d.name not in SKIP and not d.name.startswith(".")
             and C.episode_files(d) and (want is None or d.name in want)]

    recs = [migrate_book(b, a.dry_run, a.include_docs) for b in books]

    print(f"{'书':<7}{'文件':>5}{'改动':>5}{'连排':>6}{'直角':>6}{'ASCII':>7}{'单引':>5}"
          f"{'字符变化':>9}{'单边行前→后':>14}")
    for r in recs:
        d = r["chars_after"] - r["chars_before"]
        print(f"{r['书']:<7}{r['文件数']:>5}{r['改动文件']:>5}{r['doubled']:>6}{r['corner']:>6}"
              f"{r['ascii']:>7}{r['ascii_single']:>5}{d:>9}{r['unpaired_before']:>7}→{r['unpaired_after']:<6}")
    tot = {k: sum(r[k] for r in recs) for k in
           ("文件数", "改动文件", "doubled", "corner", "ascii", "ascii_single",
            "chars_before", "chars_after", "unpaired_before", "unpaired_after")}
    print(f"\n合计：文件 {tot['文件数']}，改动 {tot['改动文件']}；"
          f"连排折叠 {tot['doubled']}，直角 {tot['corner']}，ASCII双引 {tot['ascii']}，ASCII单引 {tot['ascii_single']}；"
          f"字符 {tot['chars_before']}→{tot['chars_after']}（{tot['chars_after']-tot['chars_before']:+d}）")
    print(f"单边引号行：{tot['unpaired_before']} → {tot['unpaired_after']}")

    print("\n样例（前 8 条）：")
    n = 0
    for r in recs:
        for name, old, new in r["samples"]:
            print(f"  {r['书']}/{name}\n    旧: {old}\n    新: {new}")
            n += 1
            if n >= 8:
                break
        if n >= 8:
            break

    if a.dry_run:
        print("\n[dry-run] 未写入任何文件。")
        return 0

    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = root / "_总控" / "03-体例迁移记录.md"
    lines = [f"# 标点体例迁移记录（→ 中文弯引号 “ ”）", "",
             f"> 执行时间：{now}　｜　脚本：`模板库/工具脚本/migrate_quotes.py`",
             f"> 依据：D2-2026-09-23-01（《机械门禁与校验规范.md》§二）",
             f"> 范围：{'含设定/台账文档' if a.include_docs else '仅正文 ep*.md'}　｜　"
             f"只改标点，不改文字内容", "",
             "| 书 | 文件数 | 改动文件 | 连排折叠 | 直角→弯 | ASCII双引→弯 | ASCII单引→‘’ | 字符变化 | 单边行 前→后 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in recs:
        lines.append(f"| {r['书']} | {r['文件数']} | {r['改动文件']} | {r['doubled']} | {r['corner']} | "
                     f"{r['ascii']} | {r['ascii_single']} | {r['chars_after']-r['chars_before']:+d} | "
                     f"{r['unpaired_before']}→{r['unpaired_after']} |")
    lines += [f"| **合计** | **{tot['文件数']}** | **{tot['改动文件']}** | **{tot['doubled']}** | "
              f"**{tot['corner']}** | **{tot['ascii']}** | **{tot['ascii_single']}** | "
              f"**{tot['chars_after']-tot['chars_before']:+d}** | "
              f"**{tot['unpaired_before']}→{tot['unpaired_after']}** |", "",
              "> 验证方式：迁移后重跑 `audit_library.py`，本报告中的「引号违规集」应归零；",
              "> 再抽样跑 `lint_episode.py`，A1 应为 PASS。", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[OK] 迁移记录已写入: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
