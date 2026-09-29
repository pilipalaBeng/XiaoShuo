#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复台账 repair_ledger.py v1.0

把 `00-进度清单.md` 的**集数进度表**与正文实际集数对齐：
  · 缺行（有正文、无台账行）→ 依正文与验收存档自动补行
  · 残留行（台账有行、正文已不存在，如整段废弃/删除）→ 删除该行（废弃事实另记《回滚与废弃登记表》）
已有行**一律不改**，只增/只删。表头、里程碑等其它章节不动。

用法:
    python repair_ledger.py <项目目录> [--dry-run] [--add-only|--prune-only]
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


def cell(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("|", "／")).strip()


def find_table(lines):
    """返回 (header_idx, [data_idx...], header_cells)。只认含 集/标题/状态 的表。"""
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|") or ("标题" not in s and "状态" not in s) or "集" not in s:
            continue
        header = [c.strip() for c in s.strip("|").split("|")]
        data = []
        j = i + 1
        # 跳过分隔行
        while j < len(lines):
            t = lines[j].strip()
            if not t.startswith("|"):
                break
            cs = [c.strip() for c in t.strip("|").split("|")]
            if set("".join(cs)) <= set("-: "):
                j += 1
                continue
            data.append(j)
            j += 1
        return i, data, header
    return None, [], []


def header_field(header: str, keys):
    """从文首元信息块里取某个字段的取值。"""
    if not header:
        return ""
    for line in header.splitlines():
        t = line.strip().lstrip(">").strip()
        t = re.sub(r"\*\*", "", t)
        for k in keys:
            if t.startswith(k) or (k + "：") in t or (k + ":") in t:
                v = re.split(r"[：:]", t, 1)
                if len(v) > 1:
                    return cell(v[1])[:70]
    return ""


def build_row(no, path, header, style_ep, ncol):
    title = ""
    first = path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
    if first:
        title = re.sub(r"^#+\s*", "", first[0])
        title = re.sub(r"^ep\s*\d{1,3}\s*[-—·:：]?\s*", "", title, flags=re.I)
    acc = path.parent / "验收存档" / f"ep{no:02d}-验收.md"
    status = "已验收" if acc.exists() else "已成稿"
    raw = path.read_text(encoding="utf-8", errors="replace")
    h, b = C.split_front_matter(raw)
    chars = len(C.strip_ws(h)) + len(C.strip_ws(b))
    date = _dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    rules = header_field(header, ["本集规则清单", "本集规则", "涉及规则", "本集设定"])
    newf = header_field(header, ["新埋伏笔", "新埋/推进伏笔", "伏笔"])
    backf = header_field(header, ["回收伏笔"])
    epcell = f"ep{no:02d}" if style_ep else f"{no:02d}"
    return [epcell, title, status, str(chars), rules or "—", newf or "—", backf or "—", date][:ncol]


def repair(book: Path, dry: bool, add_only: bool, prune_only: bool):
    p = book / "00-进度清单.md"
    if not p.exists():
        return None
    lines = p.read_text(encoding="utf-8").split("\n")
    hi, data, header = find_table(lines)
    if hi is None:
        return {"书": book.name, "错误": "未找到集数进度表"}

    ncol = len(header)
    eps = C.episode_files(book)
    have = {C.episode_no(x) for x in eps}
    by_no = {C.episode_no(x): x for x in eps}

    existing = {}
    for idx in data:
        cs = [c.strip() for c in lines[idx].strip().strip("|").split("|")]
        firstc = re.sub(r"^ep\s*", "", cs[0], flags=re.I)
        if re.fullmatch(r"\d{1,3}", firstc):
            existing[int(firstc)] = idx
    sample = "\n".join(lines[i] for i in data[:3])
    style_ep = bool(re.search(r"\|\s*ep\s*\d", sample, re.I)) if data else True

    missing = sorted(n for n in have if n not in existing)

    # 残留行要分两类：① 未写的计划行（状态"待写"，必须保留）
    #                ② 声称"已完成"但正文已不存在（整段废弃/删除，属虚假记录，删）
    DONE = ("已验收", "已成稿", "已交付", "已完成", "通过")
    stale_all = sorted(n for n in existing if n not in have)
    stale, planned = [], []
    for n in stale_all:
        row = lines[existing[n]]
        (planned if ("待写" in row or "计划" in row) else stale).append(n)

    added = removed = 0
    pruned_rows = []
    if not prune_only and missing:
        ins = (max(data) + 1) if data else (hi + 2)
        newlines = []
        for n in missing:
            h, _ = C.body_of(by_no[n])
            newlines.append("| " + " | ".join(build_row(n, by_no[n], h, style_ep, ncol)) + " |")
        if not dry:
            lines[ins:ins] = newlines
        added = len(newlines)
    if not add_only and stale:
        for n in sorted(stale, reverse=True):
            pruned_rows.append((n, lines[existing[n]].strip()))
            if not dry:
                del lines[existing[n]]
        removed = len(stale)

    if not dry and (added or removed):
        p.write_text("\n".join(lines), encoding="utf-8")
    return {"书": book.name, "表头": " | ".join(header), "现有行": len(existing),
            "补行": added, "删残留行": removed, "留计划行": len(planned),
            "缺行集号": missing[:12], "残留集号": stale[:12], "pruned": pruned_rows}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="台账与正文对齐")
    ap.add_argument("targets", nargs="+", help="项目目录，或书库根（自动遍历）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--add-only", action="store_true")
    ap.add_argument("--prune-only", action="store_true")
    a = ap.parse_args()

    books = []
    for t in a.targets:
        d = Path(t).resolve()
        if C.episode_files(d):
            books.append(d)
        else:
            for sub in sorted(d.iterdir()):
                if sub.is_dir() and sub.name not in SKIP and not sub.name.startswith(".") and C.episode_files(sub):
                    books.append(sub)

    for b in books:
        r = repair(b, a.dry_run, a.add_only, a.prune_only)
        if not r:
            continue
        if "错误" in r:
            print(f"{r['书']:<7} {r['错误']}")
            continue
        print(f"{r['书']:<7} 现{len(C.episode_files(b)):>3}集 台账{r['现有行']:>3}行 "
              f"补{r['补行']:>3} 删残留{r['删残留行']:>3} 留计划{r['留计划行']:>3}"
              + (f"  缺行{r['缺行集号']}" if r['缺行集号'] else "")
              + (f"  删{r['残留集号']}" if r['残留集号'] else ""))
    if a.dry_run:
        print("\n[dry-run] 未写入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
