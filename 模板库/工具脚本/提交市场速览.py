# -*- coding: utf-8 -*-
"""把市场方向速览追加登记进各项目 git（二次提交）"""
import os, subprocess

BASE = r"D:\Project"
CATEGORIES = ["百合", "萌宝", "萌宠", "灵魂互换", "打脸虐渣", "大男主", "大女主",
              "神豪系统", "末世异能", "荒岛求生", "穿越古代", "赘婿逆袭",
              "AI丧尸", "僵尸", "年代文", "生死游戏"]

for cat in CATEGORIES:
    d = os.path.join(BASE, cat)
    f = os.path.join(d, "市场方向速览.md")
    if not os.path.exists(f):
        print(f"[MISS] {cat}: 市场方向速览.md 不存在")
        continue
    env = dict(os.environ)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True, env=env)
    r = subprocess.run(["git", "commit", "-qm", f"docs: {cat} 市场方向速览（2026-09-22 调研）"],
                       cwd=d, env=env, capture_output=True, text=True)
    print(f"[OK] {cat}: commit={r.returncode == 0}")

print("ALL_DONE")
