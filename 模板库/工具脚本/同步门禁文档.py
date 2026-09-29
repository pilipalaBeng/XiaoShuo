#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步门禁文档 sync_gate_docs.py v1.0

把《机械门禁与校验规范.md》与"机械门禁"章节同步到书库内所有书（含模板库），
供新建书或规范升级后重跑。幂等：已同步的文件会被跳过。

用法:
    python sync_gate_docs.py --root D:\\Project\\XiaoShuo          # 同步
    python sync_gate_docs.py --root D:\\Project\\XiaoShuo --check  # 只检查差异
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

SPEC_NAME = "机械门禁与校验规范.md"
MARK_START = "## 六、机械门禁（必过·由脚本判定，禁止人工勾选）"

SECTION = """## 六、机械门禁（必过·由脚本判定，禁止人工勾选）

> 依据：《机械门禁与校验规范.md》§五。**机械项一律以脚本输出为准**，不应由人勾选。

运行：

```
python 模板库/工具脚本/lint_episode.py . <集数>
```

| 编号 | 校验项 | FAIL 阈值 | 判定 |
|---|---|---|---|
| A1 | 引号体例（中文弯引号 “ ”；禁 ASCII / 「」/ 连排 / 单边） | 命中即 FAIL | FAIL = 打回 |
| A2 | 破折号 | > 5 处（> 3 处 WARN） | FAIL = 打回 |
| A3 | 省略号 / 半角标点 | 命中即 FAIL | FAIL = 打回 |
| B1 | 元信息入正文（epNN / VN / 第X幕 / 检查点 / 幕末 等） | 命中即 FAIL | FAIL = 打回 |
| B2 | 编号入对话（R/V/D 编号出现在对白里） | 命中即 FAIL | FAIL = 打回 |
| C1 | 集内重复覆盖率 | > 6%（> 2.5% WARN） | FAIL = 打回 |
| C2 | 单句复读（同句去标点 ≥8 字出现 ≥3 次） | 命中即 FAIL | FAIL = 打回 |
| C3 | 跨集重复率（对最近 30 集） | > 12%（> 8% WARN） | FAIL = 打回 |
| D1 | 字数（去空白字符数） | 超出宪法区间 | FAIL = 打回 |
| D2 | 进度清单登记 | 无该集行 | FAIL = 打回 |
| D3 | 伏笔编号已登记 | 引用未登记编号 | FAIL = 打回 |
| E1 | 文首元信息块完整 | 缺项 | FAIL = 打回 |

- [ ] 已运行 `lint_episode.py`，**退出码 = 0**（无 FAIL）
- [ ] 脚本原始输出已**整段粘贴**进 `验收存档/epNN-验收.md`

**存在 FAIL 时：本集不得写"达标"，不得进入下一集。**

"""

TAIL_NOTE = ("> 机械门禁（第六节）为必过项：脚本存在 FAIL 时本集不得写入“达标”；"
             "脚本原始输出必须随验收结论存入 `验收存档/epNN-验收.md`。"
             "打回项须按《机械门禁与校验规范.md》§六 建闭环台账。\n")

HEAD_FIVE = ("## 五、文风检查（B/C 类建议项·对照文风基准与文风执行细则；"
             "A 类机械项见第六节，由脚本判定）")

AGENTS_ROW = ("| 机械门禁与校验规范.md | 机器判定：引号体例/重复率/元信息/字数/台账/伏笔编号；"
              "以脚本输出为准 | **门禁权威，每集 lint 必过** |\n")

READ_STEP = ("{n}. 交付前跑**机械门禁**：`python 模板库/工具脚本/lint_episode.py . <集数>`"
             "（有 FAIL 不放行；规范见《机械门禁与校验规范.md》）\n")


def patch_checklist(path: Path, check: bool) -> str:
    t = path.read_text(encoding="utf-8")
    if MARK_START in t:
        return "skip(已含门禁章节)"
    lines = t.splitlines(keepends=True)
    out, inserted, tail_done = [], False, False
    for i, line in enumerate(lines):
        if line.startswith("## 五、文风检查"):
            out.append(HEAD_FIVE + "\n")
            continue
        if line.startswith("## ") and "验收后必做" in line and not inserted:
            out.append(SECTION)
            inserted = True
            out.append(line)
            continue
        out.append(line)
    if not inserted:  # 没有"验收后必做"锚点，退化为追加
        out.append("\n" + SECTION)
    text = "".join(out).rstrip("\n") + "\n\n" + TAIL_NOTE
    if not check:
        path.write_text(text, encoding="utf-8")
    return "patched"


def patch_agents(path: Path, check: bool) -> str:
    t = path.read_text(encoding="utf-8")
    if SPEC_NAME in t:
        return "skip(已登记门禁规范)"
    lines = t.splitlines(keepends=True)
    out, row_done, step_done = [], False, False
    in_read = False
    last_num_idx = None
    for i, line in enumerate(lines):
        out.append(line)
        if line.startswith("## 二、读取顺序"):
            in_read = True
            continue
        if in_read and line.startswith("## "):
            if not step_done and last_num_idx is not None:
                n = int(re.match(r"^(\d+)\.", lines[last_num_idx]).group(1)) + 1
                out.insert(len(out) - 1, READ_STEP.format(n=n))
                step_done = True
            in_read = False
            continue
        if in_read and re.match(r"^\d+\.\s", line):
            last_num_idx = i
        if (not row_done) and line.startswith("| 04-每集验收清单.md |"):
            out.append(AGENTS_ROW)
            row_done = True
    if in_read and not step_done and last_num_idx is not None:
        n = int(re.match(r"^(\d+)\.", lines[last_num_idx]).group(1)) + 1
        out.append(READ_STEP.format(n=n))
        step_done = True
    if not check:
        path.write_text("".join(out), encoding="utf-8")
    return f"patched(row={row_done},step={step_done})"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    root = Path(a.root)
    tpl_dir = root / "模板库" / "小说工作流模板"
    spec_src = tpl_dir / SPEC_NAME
    if not spec_src.exists():
        print(f"[FAIL] 找不到规范母版: {spec_src}")
        return 2

    targets = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name in {"模板库", "_总控", ".workbuddy", ".git"} or d.name.startswith("."):
            continue
        if list(d.glob("ep*.md")) or list(d.glob("宪法-*.md")):
            targets.append(d)

    for d in targets:
        dst = d / SPEC_NAME
        if not dst.exists() and not a.check:
            shutil.copyfile(spec_src, dst)
        chk = d / "04-每集验收清单.md"
        ag = d / "AGENTS.md"
        rs = patch_checklist(chk, a.check) if chk.exists() else "缺文件"
        ra = patch_agents(ag, a.check) if ag.exists() else "缺文件"
        print(f"{d.name:<7} 规范={'new' if not dst.exists() else 'exist'}  验收清单={rs}  AGENTS={ra}")

    tchk = tpl_dir / "04-每集验收清单-模板.md"
    if tchk.exists():
        print(f"{'模板库':<7} 验收清单={patch_checklist(tchk, a.check)}")
    print(f"\n处理书数 {len(targets)}；{'（检查模式，未写入）' if a.check else '已写入'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
