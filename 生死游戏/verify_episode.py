#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《九局归零》(生死游戏) 每集机械校验脚本（由荒野规则版适配）。
用法: python verify_episode.py <项目根目录> <集数两位,如 01>
校验项:
  1. epNN-*.md 正文文件存在
  2. 正文字数在 2000-2600 区间（宪法参数区；中文按字符计，剔除空白与头部标注）
  3. 00-进度清单.md 已登记该集
  4. 01-动态状态库.md 与 伏笔活表-生死游戏.md 的修改时间不早于正文文件（说明已更新）
脚本只做机械兜底，不能替代验收清单与独立审核。
"""
import re
import sys
from pathlib import Path


def count_chars(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def main() -> int:
    if len(sys.argv) != 3:
        print("用法: python verify_episode.py <项目根目录> <集数两位, 如 01>")
        return 2

    root = Path(sys.argv[1])
    ep = sys.argv[2].zfill(2)
    if not root.is_dir():
        print(f"[FAIL] 项目根目录不存在: {root}")
        return 1

    matches = list(root.glob(f"ep{ep}-*.md"))
    if not matches:
        print(f"[FAIL] 未找到正文文件 ep{ep}-*.md")
        return 1
    body_path = matches[0]
    body_text = body_path.read_text(encoding="utf-8", errors="replace")
    n = count_chars(body_text)
    print(f"[OK] 正文文件: {body_path.name}")

    if 2000 <= n <= 2600:
        print(f"[OK] 字数 {n} 在 2000-2600 区间")
    else:
        print(f"[WARN] 字数 {n} 不在 2000-2600 区间（宪法参数区，需人工判断）")

    prog = root / "00-进度清单.md"
    if not prog.exists():
        print(f"[FAIL] 缺少进度清单: {prog.name}")
        return 1
    ptext = prog.read_text(encoding="utf-8", errors="replace")
    if ep in ptext:
        ok_words = ["通过", "验收", "达标", "已完成", "待确认", "已交付", "初稿"]
        hit = [w for w in ok_words if w in ptext]
        print(f"[OK] 进度清单已登记 ep{ep}，状态词命中: {hit or '未命中(需人工看)'}")
    else:
        print(f"[FAIL] 进度清单未登记 ep{ep}")
        return 1

    for name in ["01-动态状态库.md", "伏笔活表-生死游戏.md"]:
        f = root / name
        if not f.exists():
            print(f"[FAIL] 缺少状态文件: {name}")
            return 1
        if f.stat().st_mtime >= body_path.stat().st_mtime:
            print(f"[OK] {name} 修改时间不早于正文（已更新）")
        else:
            print(f"[WARN] {name} 修改时间早于正文，可能未随本集更新，需人工确认")

    print("\n结论: 机械校验完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
