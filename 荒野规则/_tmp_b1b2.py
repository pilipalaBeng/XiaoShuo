import sys, json, subprocess
eps = [10,25,29,30,39,48,54,55,56,57,58,59,60,62,63,75,79,80,81,84,85,86,87,88,89,90]
with open("_b1b2_report.txt","w",encoding="utf-8") as f:
    for e in eps:
        out = subprocess.run([sys.executable, r"..\模板库\工具脚本\lint_episode.py", ".", str(e), "--json"],
                             capture_output=True, text=True, encoding="utf-8")
        d = json.loads(out.stdout)
        for c in d["checks"]:
            if c["id"] in ("B1","B2"):
                f.write(f'== ep{e:02d} {c["id"]} {c["status"]}\n')
                for line in c["detail"]:
                    f.write("    " + line.strip() + "\n")
