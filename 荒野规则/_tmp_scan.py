import sys, json, subprocess, os, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
eps = [10,25,29,30,39,48,54,55,56,57,58,59,60,62,63,75,79,80,81,84,85,86,87,88,89,90]
print("now", time.strftime("%H:%M:%S"))
for e in eps:
    fn = [x for x in os.listdir(".") if x.startswith("ep%02d-" % e)]
    fn = fn[0] if fn else "?"
    mt = time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(fn)))
    out = subprocess.run([sys.executable, r"..\模板库\工具脚本\lint_episode.py", ".", str(e), "--json"],
                         capture_output=True, text=True, encoding="utf-8")
    d = json.loads(out.stdout)
    st = {c["id"]: (c["status"], c["detail"]) for c in d["checks"]}
    b1s, b1d = st["B1"]
    line = f"ep{e:02d} mtime={mt} B1={b1s}"
    if b1s != "PASS":
        line += " :: " + " || ".join(x.strip() for x in b1d[1:])
    print(line)
