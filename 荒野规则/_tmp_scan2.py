import sys, json, subprocess, os, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
eps = [10,25,29,30,39,48,54,55,56,57,58,59,60,62,63,75,79,80,81,84,85,86,87,88,89,90]
print("now", time.strftime("%H:%M:%S"))
bad_b1, bad_b2 = [], []
for e in eps:
    out = subprocess.run([sys.executable, r"..\模板库\工具脚本\lint_episode.py", ".", str(e), "--json"],
                         capture_output=True, text=True, encoding="utf-8")
    d = json.loads(out.stdout)
    st = {c["id"]: (c["status"], c["detail"]) for c in d["checks"]}
    b1s, b1d = st["B1"]; b2s, b2d = st["B2"]
    if b1s != "PASS":
        bad_b1.append(e)
        print(f"ep{e:02d} B1={b1s} :: " + " || ".join(x.strip() for x in b1d[1:]))
    if b2s != "PASS":
        bad_b2.append(e)
        print(f"ep{e:02d} B2={b2s} :: " + " || ".join(x.strip() for x in b2d[1:]))
print("B1 not PASS:", bad_b1)
print("B2 not PASS:", bad_b2)
