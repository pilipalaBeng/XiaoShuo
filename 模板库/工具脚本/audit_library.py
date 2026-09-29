#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全库机械巡检 audit_library.py v1.0（《XiaoShuo 书库》通用）

一次跑完所有书的机械健康度，输出 Markdown 报告（默认 _总控/02-机械巡检报告.md）。
它只做机器能判的事：体例/重复/台账/幽灵条目/大纲缺口——不做文学判断。

用法:
    python audit_library.py                        # 巡检当前书库
    python audit_library.py --root D:\\Project\\XiaoShuo
    python audit_library.py --out _总控\\02-机械巡检报告.md
    python audit_library.py --stdout-only
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import novel_lint_core as C  # noqa: E402

SKIP = {"模板库", "_总控", ".workbuddy", ".git", "验收存档"}


def books(root: Path):
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name in SKIP or d.name.startswith("."):
            continue
        if C.episode_files(d) or (d / "宪法-{}.md".format(d.name)).exists() or list(d.glob("宪法-*.md")):
            out.append(d)
    return out


def audit_book(root: Path):
    eps = C.episode_files(root)
    r = {
        "书": root.name, "集数": len(eps), "chars": 0, "han": 0,
        "style": {}, "dash_over": [], "intra_over": [], "cross_over": [],
        "meta_fail": {}, "sent_dup": [], "dup_groups": {},
        "ledger_rows": 0, "ledger_max": 0, "missing": [], "claim_delta": None,
        "accept": 0, "outline_missing_copy": [], "outlines": [],
        "word_range": C.detect_word_range(root), "below": 0, "above": 0,
        "fs_ids": 0, "fs_unknown": [], "ghosts": [], "agents_empty": None,
        "worst": [],
    }
    if not eps:
        return r

    style_counter = {}
    bodies = {}
    ledger = C.load_ledger(root)
    r["ledger_rows"] = len(ledger)
    r["ledger_max"] = max(ledger) if ledger else 0
    claim_total = 0
    claim_n = 0

    lo, hi, _ = r["word_range"]
    fps = []
    for p in eps:
        no = C.episode_no(p)
        text = p.read_text(encoding="utf-8", errors="replace")
        header, body = C.split_front_matter(text)
        chars = len(C.strip_ws(body)) + len(C.strip_ws(header))
        r["chars"] += chars
        r["han"] += C.han_count(body)
        if chars < lo:
            r["below"] += 1
        if chars > hi:
            r["above"] += 1
        style = C.quote_style(text)
        style_counter[style] = style_counter.get(style, 0) + 1

        d = C.dash_count(body)
        if d > C.TH["dash_fail"]:
            r["dash_over"].append((no, d))

        ratio, _ = C.intra_repetition(body)
        if ratio > C.TH["intra_rep_fail"]:
            r["intra_over"].append((no, ratio))

        sd = C.sentence_dupes(body)
        if sd:
            r["sent_dup"].append((no, len(sd), sd[0]))

        mf, _mw = C.meta_hits(body)
        if mf:
            r["meta_fail"][no] = len(mf)

        cur = C.shingle_set(body)
        best, best_ep = 0.0, ""
        for old_no, old_fp in fps[-C.TH["cross_window"]:]:
            c = C.containment(cur, old_fp)
            if c > best:
                best, best_ep = c, old_no
        if best > C.TH["cross_rep_fail"]:
            r["cross_over"].append((no, best, best_ep))
        fps.append((no, cur))

        dg = C.body_digest(body)
        bodies.setdefault(dg, []).append(no)

        fail_n = 0
        if C.quote_census(text)["ascii"] or C.quote_census(text)["corner"]:
            fail_n += 1
        if d > C.TH["dash_fail"]:
            fail_n += 1
        if ratio > C.TH["intra_rep_fail"]:
            fail_n += 1
        if sd:
            fail_n += 1
        if mf:
            fail_n += 1
        if best > C.TH["cross_rep_fail"]:
            fail_n += 1
        if no not in ledger:
            fail_n += 1
        r["worst"].append((fail_n, no, round(ratio, 1), round(best, 1), len(mf)))

        row = ledger.get(no)
        if row and row.get("claimed"):
            claim_total += row["claimed"]
            claim_n += 1

    r["style"] = style_counter
    r["dup_groups"] = {k: v for k, v in bodies.items() if len(v) > 1}
    r["missing"] = [no for no, _ in [(C.episode_no(p), p) for p in eps] if no not in ledger]
    if claim_n:
        r["claim_delta"] = (claim_total, r["chars"], round((claim_total / max(1, r["chars"]) - 1) * 100, 1))
    r["accept"] = len(C.acceptance_files(root))

    real, sus = C.load_outline_files(root)
    r["outlines"], r["outline_missing_copy"] = real, sus

    ids, _ = C.load_foreshadow_ids(root)
    r["fs_ids"] = len(ids)
    used = set()
    for p in eps:
        txt = p.read_text(encoding="utf-8", errors="replace")
        used |= {"V" + m for m in __import__("re").findall(r"(?<![A-Za-z])V\s*(\d{1,2})(?![0-9])", txt)}
    r["fs_unknown"] = sorted(used - ids, key=lambda x: int(x[1:]))

    for name in C.load_characters(root)[:60]:
        if C.count_in_episodes(root, name) == 0:
            r["ghosts"].append(name)

    r["agents_empty"] = C.agents_progress_empty(root)
    r["worst"].sort(reverse=True)
    return r


def render(reports, root: Path) -> str:
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = []
    A = L.append
    A(f"# 《XiaoShuo 书库》机械巡检报告")
    A("")
    A(f"> 生成时间：{now}　｜　工具：`模板库/工具脚本/audit_library.py` v{C.VERSION}")
    A(f"> 依据：《{C.SPEC_FILE}》《小说写作通用规则.md》　｜　标点体例（D2 裁决 2026-09-23）：全库统一 **中文弯引号 “ ”**")
    A("> 本报告只含机械判定，不含文学评价；判定为 FAIL 的集不等于不可用，但**不得再标注为“达标”**。")
    A("")
    A("## 一、总览")
    A("")
    A("| 书 | 集数 | 去空白字符 | 均字/集 | 引号体例 | 字数达标 | 引号违规集 | 破折号超限 | 集内重复超限 | 跨集重复超限 | 重复正文组 | 台账登记 | 验收存档 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    tot_chars = tot_eps = 0
    for r in reports:
        if not r["集数"]:
            A(f"| {r['书']} | 0 | 0 | — | — | — | — | — | — | — | — | {r['ledger_rows']} | {r['accept']} |")
            continue
        tot_chars += r["chars"]
        tot_eps += r["集数"]
        lo, hi, _ = r["word_range"]
        style = "、".join(f"{k}×{v}" for k, v in sorted(r["style"].items(), key=lambda t: -t[1]))
        quo_bad = sum(v for k, v in r["style"].items() if k != "中文弯引号" and k != "无对话引号")
        dup_groups = sum(len(v) for v in r["dup_groups"].values())
        A(f"| {r['书']} | {r['集数']} | {r['chars']:,} | {r['chars'] // max(1, r['集数'])} | {style} | "
          f"{r['集数'] - r['below'] - r['above']}/{r['集数']} | {quo_bad} | {len(r['dash_over'])} | "
          f"{len(r['intra_over'])} | {len(r['cross_over'])} | {dup_groups or '—'} | "
          f"{r['ledger_rows']}/{r['集数']} | {r['accept']} |")
    A(f"| **合计** | **{tot_eps}** | **{tot_chars:,}** | — | — | — | — | — | — | — | — | — | — |")
    A("")

    A("## 二、逐书明细")
    for r in reports:
        if not r["集数"]:
            continue
        A("")
        A(f"### {r['书']}（{r['集数']} 集 / {r['chars']:,} 字 / 汉字 {r['han']:,}）")
        lo, hi, src = r["word_range"]
        A(f"- 字数区间 {lo}-{hi}（{src}）：低于下限 {r['below']} 集，高于上限 {r['above']} 集")
        if r["claim_delta"]:
            cl, ac, pct = r["claim_delta"]
            A(f"- 进度清单声称合计 {cl:,} 字 vs 实测 {ac:,} 字（偏差 {pct:+.1f}%）")
        A(f"- 台账：00-进度清单登记 {r['ledger_rows']}/{r['集数']} 行；"
          f"验收存档 {r['accept']} 份；AGENTS.md 进度区" +
          ("**仍为空模板**" if r["agents_empty"] else ("已填" if r["agents_empty"] is False else "无此节")))
        if r["missing"]:
            A(f"- 台账缺口：未登记集号 {r['missing'][:24]}{' …' if len(r['missing']) > 24 else ''}")
        if r["outlines"]:
            A(f"- 幕级大纲：{'、'.join(r['outlines'])}")
        if r["outline_missing_copy"]:
            A(f"- ⚠ 疑似占位副本（内容为第一幕大纲）：{'、'.join(r['outline_missing_copy'])}")
        if not r["outlines"]:
            A("- ⚠ **无任何幕级大纲文件**")
        if r["dup_groups"]:
            for k, v in sorted(r["dup_groups"].items(), key=lambda t: -len(t[1])):
                A(f"- ⚠ **正文逐字节相同 {len(v)} 集**：{', '.join('ep%02d' % n for n in v)}")
        if r["dash_over"]:
            top = sorted(r["dash_over"], key=lambda t: -t[1])[:8]
            A(f"- 破折号超限 {len(r['dash_over'])} 集，最多： " +
              "、".join(f"ep{n:02d}({d})" for n, d in top))
        if r["intra_over"]:
            top = sorted(r["intra_over"], key=lambda t: -t[1])[:8]
            A(f"- 集内重复超限 {len(r['intra_over'])} 集，最高： " +
              "、".join(f"ep{n:02d}({v}%)" for n, v in top))
        if r["cross_over"]:
            top = sorted(r["cross_over"], key=lambda t: -t[1])[:6]
            A(f"- 跨集重复超限 {len(r['cross_over'])} 集，最高： " +
              "、".join(f"ep{n:02d}({v}%≈ep{o:02d})" for n, v, o in top))
        if r["meta_fail"]:
            top = sorted(r["meta_fail"].items(), key=lambda t: -t[1])[:6]
            A(f"- 元信息入正文 {len(r['meta_fail'])} 集，最多： " +
              "、".join(f"ep{n:02d}({c}处)" for n, c in top))
        if r["sent_dup"]:
            top = sorted(r["sent_dup"], key=lambda t: -t[1])[:5]
            A("- 单句复读集：" + "、".join(f"ep{n:02d}({c}句)" for n, c, _ in top))
        A(f"- 伏笔活表登记 {r['fs_ids']} 条" +
          (f"；⚠ 正文引用但未登记：{', '.join(r['fs_unknown'][:12])}" if r["fs_unknown"] else "；引用编号全部已登记"))
        if r["ghosts"]:
            A(f"- 幽灵条目候选（人物档案有卡、正文 0 命中，需人工确认）：{', '.join(r['ghosts'][:12])}")
        if r["worst"]:
            A("- 问题最多的集（FAIL 项数 / 集内重复% / 跨集重复% / 元信息处数）：")
            for f, n, ir, cr, mf in r["worst"][:6]:
                A(f"    - ep{n:02d}：FAIL {f} 项（集内 {ir}% / 跨集 {cr}% / 元信息 {mf} 处）")

    A("")
    A("## 三、全库处置建议（按机械证据排序）")
    A("")
    A("1. **P0 停写**：任何 集内重复 >3% / 跨集重复 >12% / 正文与旧集逐字节相同的书，先停止续写，回到大纲层。")
    A("2. **P0 统一体例**：ASCII 直引号与直角引号全部转为中文弯引号 “ ”，迁移脚本另批执行；迁移后本书引号违规集应归零。")
    A("3. **P1 台账对齐**：补齐 00-进度清单缺失行，并停止虚报字数（以本报告实测为准）。")
    A("4. **P1 元信息清理**：正文内的 epNN / VN / 第X幕 / 检查点 / 幕末 等创作标记逐处删除。")
    A("5. **P2 大纲门禁**：无本幕大纲的集不得产出；占位副本（幕级大纲-待规划）须替换为真实大纲或删除。")
    A("")
    A("> 本报告由脚本生成，可重复执行比对；修复后重跑即可验证。")
    return "\n".join(L)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="全库机械巡检")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--out", default=None)
    ap.add_argument("--stdout-only", action="store_true")
    a = ap.parse_args()

    root = Path(a.root)
    bs = books(root)
    reports = []
    for b in bs:
        reports.append(audit_book(b))

    md = render(reports, root)
    out = Path(a.out) if a.out else root / "_总控" / "02-机械巡检报告.md"
    if not a.stdout_only:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"[OK] 报告已写入: {out}")
    if a.stdout_only:
        print(md)
    else:
        print(f"巡检书数 {len(reports)}；总集数 {sum(r['集数'] for r in reports)}；"
              f"总字数 {sum(r['chars'] for r in reports):,}")
        for r in reports:
            if not r["集数"]:
                continue
            dup = sum(len(v) for v in r["dup_groups"].values())
            flag = "⚠" if (dup or r["intra_over"] or r["cross_over"]) else " "
            print(f" {flag} {r['书']:<6} 集{r['集数']:>3} 字{r['chars']:>7,} "
                  f"重复组{dup:>3} 集内超限{len(r['intra_over']):>3} 跨集超限{len(r['cross_over']):>3} "
                  f"破折号超限{len(r['dash_over']):>3} 台账{r['ledger_rows']:>3}/{r['集数']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
