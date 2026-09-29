#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单集机械门禁 lint_episode.py v1.0（《XiaoShuo 书库》通用）

替代并升级原 verify_episode.py（原脚本只查 5 件事，且有 3 个缺陷：
字数把文首元信息算进去、进度清单用子串匹配、状态词在全文命中即算登记）。

用法:
    python lint_episode.py <项目根目录> <集数>            # 单集门禁
    python lint_episode.py <项目根目录> --all             # 全书逐集
    python lint_episode.py <项目根目录> <集数> --json     # 机器可读

判定:
    退出码 0 = 通过（无 FAIL）；1 = 打回（有 FAIL）；2 = 用法错误（含文件缺失）。
    有 FAIL 时不得在 验收存档 写"达标"。
    本脚本输出必须原样粘贴进 验收存档/epNN-验收.md（见《机械门禁与校验规范.md》§5）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import novel_lint_core as C  # noqa: E402


def _fmt_items(items, limit=4):
    out = []
    for it in items[:limit]:
        out.append("      · " + " | ".join(str(x) for x in it))
    if len(items) > limit:
        out.append(f"      · …另有 {len(items) - limit} 处")
    return out


def lint_one(root: Path, no: int, word_range=None):
    """返回 (checks, summary)。checks 为 [(编号, 说明, 状态, 详情行列表)]"""
    eps = C.episode_files(root)
    target = next((p for p in eps if C.episode_no(p) == no), None)
    if target is None:
        return None, {"error": f"未找到 ep{no:02d}-*.md"}

    header, body = C.body_of(target)
    chars = len(C.strip_ws(body)) + len(C.strip_ws(header))
    body_chars = len(C.strip_ws(body))
    han = C.han_count(body)
    book_style = C.book_quote_style(root)
    checks = []

    # ---- A1 引号体例（D2 裁决：全库统一 “ ”）
    q = C.quote_census(target.read_text(encoding="utf-8", errors="replace"))
    det = [f"中文弯引号 {q['cn_open']}/{q['cn_close']}；ASCII直引号 {q['ascii']}；"
           f"直角引号 {q['corner']}；连排 {q['doubled_ascii']}/{q['doubled_cn']}；"
           f"单边行 {len(q['unpaired_lines'])}"]
    if q["ascii"] or q["corner"]:
        det.append(f"      本集体例：{q['style']}；全书主导体例：{book_style}（应为 中文弯引号）")
        if q["style"] == book_style and book_style != "中文弯引号":
            det.append("      注：本书尚未执行体例迁移（全库统一切换事项，非本集独有问题）")
        checks.append(("A1", "引号体例", "FAIL", det))
    elif q["unpaired_lines"]:
        det.append(f"      单边引号行号：{q['unpaired_lines'][:10]}")
        checks.append(("A1", "引号体例", "FAIL", det))
    elif not q["cn_open"]:
        checks.append(("A1", "引号体例", "WARN", det + ["      本集无对话引号（确认是否整集无对白）"]))
    else:
        checks.append(("A1", "引号体例", "PASS", det))

    # ---- A2 破折号
    d = C.dash_count(body)
    st = "FAIL" if d > C.TH["dash_fail"] else ("WARN" if d > C.TH["dash_warn"] else "PASS")
    checks.append(("A2", "破折号", st, [f"本集 {d} 处（上限 {C.TH['dash_fail']}，警戒 {C.TH['dash_warn']}）"]))

    # ---- A3 省略号 / 半角标点
    dots = re.findall(r"\.\.\.", body)
    halfw = re.findall(r"[\u4e00-\u9fa5][,;:!?]", body)
    det = [f"三点省略号 {len(dots)}；中文后半角标点 {len(halfw)}"]
    st = "FAIL" if (dots or halfw) else "PASS"
    if dots:
        det += _fmt_items([(m.start(),) for m in re.finditer(r"\.\.\.", body)], 3)
    checks.append(("A3", "省略号/半角标点", st, det))

    # ---- B1 元信息入正文
    fail, warn = C.meta_hits(body)
    if fail:
        checks.append(("B1", "元信息入正文", "FAIL",
                       [f"命中 {len(fail)} 处（创作标记不得出现在正文）"] + [
                           f"      · L{i} [{lab}] {txt}" for i, lab, txt in fail[:5]]))
    elif warn:
        checks.append(("B1", "元信息入正文", "WARN",
                       [f"疑似 {len(warn)} 处（人工确认是否叙事用语）"] + [
                           f"      · L{i} [{lab}] {txt}" for i, lab, txt in warn[:5]]))
    else:
        checks.append(("B1", "元信息入正文", "PASS", ["无创作层标记"]))

    # ---- B2 编号入对话
    #  V/D 属作者层索引（伏笔编号），角色说出即 FAIL；
    #  R/C 属"待 D2 裁决"（面板与角色是否使用规则编号），故降为 WARN，与 §二 D2-04 一致。
    rd = C.rule_id_in_dialogue(body)
    hard = [x for x in rd if x[1].startswith(("V", "D"))]
    soft = [x for x in rd if x[1].startswith(("R", "C"))]
    if hard:
        checks.append(("B2", "编号入对话", "FAIL",
                       [f"{len(hard)} 处（角色不应说出 V/D 编号）"] + [
                           f"      · L{i} {rid} {txt}" for i, rid, txt in hard[:5]]))
    elif soft:
        checks.append(("B2", "编号入对话", "WARN",
                       [f"{len(soft)} 处 R/C 规则编号入对白（待 D2-01 裁决，不阻塞）"] + [
                           f"      · L{i} {rid} {txt}" for i, rid, txt in soft[:3]]))
    else:
        checks.append(("B2", "编号入对话", "PASS", ["无"]))

    # ---- C1 集内重复
    ratio, top = C.intra_repetition(body)
    st = "FAIL" if ratio > C.TH["intra_rep_fail"] else ("WARN" if ratio > C.TH["intra_rep_warn"] else "PASS")
    det = [f"重复覆盖率 {ratio}%（上限 {C.TH['intra_rep_fail']}%，警戒 {C.TH['intra_rep_warn']}%）"
           "　口径：落在重复片段内的内容字符占比（已去标点）"]
    det += [f"      · 高频片段「{s}」×{c}" for s, c in top if c >= 2][:3]
    checks.append(("C1", "集内重复率", st, det))

    # ---- C2 单句复读
    sd = C.sentence_dupes(body)
    if sd:
        checks.append(("C2", "单句复读", "FAIL",
                       [f"{len(sd)} 句重复 ≥{C.TH['sent_dup_fail']} 次"] + [
                           f"      · ×{c}「{s[:40]}」" for s, c in sd]))
    else:
        checks.append(("C2", "单句复读", "PASS", ["无"]))

    # ---- C3 跨集重复
    cross, cross_ep = C.cross_repetition(root, target)
    st = "FAIL" if cross > C.TH["cross_rep_fail"] else ("WARN" if cross > C.TH["cross_rep_warn"] else "PASS")
    checks.append(("C3", "跨集重复率", st,
                   [f"与最近 {C.TH['cross_window']} 集的最大重合 {cross}%"
                    f"（上限 {C.TH['cross_rep_fail']}%）" + (f"，最相似：{cross_ep}" if cross_ep else "")]))

    # ---- D1 字数（给 1%/20 字容差，避免恰好卡在边界上翻来覆去）
    lo, hi, src = word_range or C.detect_word_range(root)
    tol = max(20, int(lo * 0.01))
    st = "PASS" if (lo - tol) <= chars <= (hi + tol) else "FAIL"
    checks.append(("D1", "字数", st,
                   [f"去空白字符 {chars}（正文 {body_chars} / 汉字 {han}）；"
                    f"区间 {lo}-{hi}（容差 ±{tol}，来源：{src}）"]))

    # ---- D2 台账登记（字数口径可能记"去空白"或"汉字"，两者任一吻合即通过）
    ledger = C.load_ledger(root)
    row = ledger.get(no)
    if row is None:
        checks.append(("D2", "进度清单登记", "FAIL", [f"00-进度清单.md 无 ep{no:02d} 行"]))
    else:
        claimed = row["claimed"]
        if not claimed:
            checks.append(("D2", "进度清单登记", "PASS", ["已登记（未解析到字数）"]))
        else:
            tol = max(120, chars * 0.08)
            ok = abs(claimed - chars) <= tol or abs(claimed - han) <= tol
            checks.append(("D2", "进度清单登记", "PASS" if ok else "WARN",
                           [f"已登记，清单声称 {claimed} 字；实测 去空白 {chars} / 汉字 {han}"
                            + ("" if ok else f"（与两种口径均差 >8%）")]))

    # ---- D3 伏笔编号合法性
    ids, fpath = C.load_foreshadow_ids(root)
    used = set(re.findall(r"(?<![A-Za-z])V\s*(\d{1,2})(?![0-9])", body + header))
    used = {"V" + u for u in used}
    unknown = sorted(used - ids, key=lambda x: int(x[1:]))
    if fpath is None:
        checks.append(("D3", "伏笔编号", "WARN", ["未找到 伏笔活表-*.md，无法核对"]))
    elif unknown:
        checks.append(("D3", "伏笔编号", "FAIL",
                       [f"正文引用但活表未登记：{', '.join(unknown)}（活表已登记 {len(ids)} 条）"]))
    else:
        checks.append(("D3", "伏笔编号", "PASS", [f"引用编号均已登记（活表 {len(ids)} 条）"]))

    # ---- E1 文首元信息块（各书表头体例不同：> 引用式 / YAML 式 / HTML 注释式）
    need = []
    if not any(k in header for k in ("涉及人物", "人物:", "人物：")):
        need.append("涉及人物")
    if not any(k in header for k in ("本集规则", "涉及规则", "规则状态", "规则:", "规则：")):
        need.append("本集规则/涉及规则")
    checks.append(("E1", "文首元信息块", "FAIL" if need else "PASS",
                   ["缺少：" + "、".join(need) if need else "完整（人物 + 规则）"]))

    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for _, _, s, _ in checks:
        counts[s] += 1
    summary = {
        "root": str(root), "episode": f"ep{no:02d}", "file": target.name,
        "chars": chars, "body_chars": body_chars, "han": han,
        "verdict": "打回" if counts["FAIL"] else "通过",
        "counts": counts,
    }
    return checks, summary


def dq_label(q):
    return f" {q['doubled_ascii']}/{q['doubled_cn']}" if (q["doubled_ascii"] or q["doubled_cn"]) else " 0/0"


def render(root: Path, no: int, checks, summary) -> str:
    lines = []
    lines.append("=" * 68)
    lines.append(f"机械门禁输出 · lint_episode v{C.VERSION}")
    lines.append(f"项目: {root.name}    集: {summary['episode']}    文件: {summary['file']}")
    lines.append(f"依据: {C.SPEC_FILE} §3/§4；《小说写作通用规则.md》§一~§五")
    lines.append("=" * 68)
    for cid, name, st, det in checks:
        lines.append(f"[{st}] {cid} {name}")
        lines.extend(det)
    cs = summary["counts"]
    lines.append("-" * 68)
    lines.append(f"汇总: PASS {cs['PASS']} / WARN {cs['WARN']} / FAIL {cs['FAIL']}"
                 f"  →  判定: {summary['verdict']}")
    if cs["FAIL"]:
        lines.append("处置: 存在 FAIL，按《机械门禁与校验规范.md》§5 打回，不得写“达标”。")
    else:
        lines.append("处置: 机械项通过；内容项仍须按 04-每集验收清单 人工/审核判定。")
    lines.append("=" * 68)
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="单集机械门禁")
    ap.add_argument("root", help="项目根目录")
    ap.add_argument("episode", nargs="?", help="集数（如 12 或 ep12）")
    ap.add_argument("--all", action="store_true", help="逐集巡检全书")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--min", type=int, default=None, help="覆盖字数下限")
    ap.add_argument("--max", type=int, default=None, help="覆盖字数上限")
    a = ap.parse_args()

    root = Path(a.root)
    if not root.is_dir():
        print(f"[FAIL] 项目根目录不存在: {root}")
        return 2
    root = root.resolve()   # 支持 . 与相对路径，便于"在书目录内"运行

    word_range = None
    if a.min or a.max:
        d_lo, d_hi, _ = C.detect_word_range(root)
        word_range = (a.min or d_lo, a.max or d_hi, "命令行覆盖")

    if a.all:
        worst, bad = [], 0
        for p in C.episode_files(root):
            no = C.episode_no(p)
            checks, summary = lint_one(root, no, word_range)
            if checks is None:
                continue
            cs = summary["counts"]
            if cs["FAIL"]:
                bad += 1
            worst.append((cs["FAIL"], no, summary["verdict"]))
        worst.sort(reverse=True)
        print(f"=== {root.name} 逐集门禁汇总 ===")
        print(f"总集数 {len(worst)}；打回 {bad} 集；通过 {len(worst) - bad} 集")
        print("FAIL 最多的 15 集：")
        for f, no, v in worst[:15]:
            print(f"  ep{no:02d}  FAIL={f}  {v}")
        return 0 if bad == 0 else 1

    if not a.episode:
        print("用法: python lint_episode.py <项目根目录> <集数> [--json|--all]")
        return 2
    no = int(re.sub(r"\D", "", a.episode) or 0)
    checks, summary = lint_one(root, no, word_range)
    if checks is None:
        print(f"[FAIL] {summary['error']}")
        return 2
    if a.json:
        print(json.dumps({"summary": summary,
                          "checks": [{"id": c, "name": n, "status": s, "detail": d} for c, n, s, d in checks]},
                         ensure_ascii=False, indent=2))
    else:
        print(render(root, no, checks, summary))
    return 1 if summary["counts"]["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
