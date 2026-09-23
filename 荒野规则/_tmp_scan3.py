import sys, json, subprocess, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
eps = sorted(int(x[2:4]) for x in os.listdir(".") if x.startswith("ep") and x.endswith(".md") and x[2:4].isdigit())
bad = []
for e in eps:
    out = subprocess.run([sys.executable, r"..\模板库\工具脚本\lint_episode.py", ".", str(e), "--json"],
                         capture_output=True, text=True, encoding="utf-8")
    d = json.loads(out.stdout)
    st = {c["id"]: (c["status"], c["detail"]) for c in d["checks"]}
    b1s, b1d = st["B1"]
    if b1s != "PASS":
        bad.append((e, b1s, " || ".join(x.strip() for x in b1d[1:])))
print("total eps:", len(eps))
print("B1 not PASS across whole book:", len(bad))
for e,s,t in bad: print(f"  ep{e:02d} {s} :: {t}")
