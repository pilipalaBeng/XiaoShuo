# -*- coding: utf-8 -*-
"""批量创建 16 个小说项目骨架（从模板包复制 + 参数替换 + git init）"""
import os, shutil, subprocess

TPL = r"D:\Project\模板库\小说工作流模板"
BASE = r"D:\Project"

CATEGORIES = ["百合", "萌宝", "萌宠", "灵魂互换", "打脸虐渣", "大男主", "大女主",
              "神豪系统", "末世异能", "荒岛求生", "穿越古代", "赘婿逆袭",
              "AI丧尸", "僵尸", "年代文", "生死游戏"]

RULER_A = "A 短剧爽文档"
RULER_B = "B 规则怪谈/无限流档"
RULER_C = "C 都市言情/情感流档"
RULER = {cat: (RULER_B if cat in ("僵尸", "生死游戏")
               else RULER_C if cat in ("百合", "大女主", "萌宠", "年代文", "灵魂互换")
               else RULER_A) for cat in CATEGORIES}

COPY_MAP = [
    ("AGENTS-模板.md", "AGENTS.md"),
    ("宪法-模板.md", "宪法-{cat}.md"),
    ("07-工作流总纲-模板.md", "07-工作流总纲.md"),
    ("01-动态状态库-模板.md", "01-动态状态库.md"),
    ("伏笔活表-模板.md", "伏笔活表-{cat}.md"),
    ("00-进度清单-模板.md", "00-进度清单.md"),
    ("04-每集验收清单-模板.md", "04-每集验收清单.md"),
    ("机械门禁与校验规范.md", "机械门禁与校验规范.md"),
    ("回滚与废弃登记表-模板.md", "回滚与废弃登记表.md"),
    ("审核Agent职责-模板.md", "审核Agent职责-{cat}.md"),
    ("文风基准-模板.md", "文风基准-{cat}.md"),
    ("术语表-模板.md", "术语表-{cat}.md"),
    ("05-竞品拆解-模板.md", "05-竞品拆解档案.md"),
    ("06-发布运营-模板.md", "06-发布运营计划.md"),
    ("幕级大纲-模板.md", "幕级大纲-待规划.md"),
]

for cat in CATEGORIES:
    d = os.path.join(BASE, cat)
    os.makedirs(d, exist_ok=True)
    for src_name, dst_name in COPY_MAP:
        src = os.path.join(TPL, src_name)
        dst = os.path.join(d, dst_name.replace("{cat}", cat))
        with open(src, "r", encoding="utf-8") as f:
            text = f.read()
        text = text.replace("{{书名}}", cat)
        if dst_name.startswith("宪法"):
            text = text.replace("- 题材 / 类型：", f"- 题材 / 类型：{cat}")
            text = text.replace("- 目标平台（番茄 / 起点 / 七猫 / 短剧平台 / 其他）：",
                                "- 目标平台：个人创作（暂不上平台）")
            text = text.replace("- 验收尺子档位（对应 04-验收清单题材尺子表）：",
                                f"- 验收尺子档位：{RULER[cat]}（节奏指标按 04-验收清单〇节该档替换）")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(text)
    # git init + 首提交
    env = dict(os.environ)
    subprocess.run(["git", "init", "-q"], cwd=d, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "KouDiuSang"], cwd=d, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "koudiusang@local"], cwd=d, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True, env=env)
    r = subprocess.run(["git", "commit", "-qm", f"init: {cat} 项目骨架（模板包 v1.0）"],
                       cwd=d, env=env, capture_output=True, text=True)
    print(f"[OK] {cat}: 13 files, commit={r.returncode == 0}")

print("ALL_DONE")
