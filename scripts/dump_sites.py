"""Print a compact view of captured site info for writing details. Usage: python3 scripts/dump_sites.py 2021 [--todo]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_site as b

year = sys.argv[1]
todo = "--todo" in sys.argv
sites = json.loads((b.ROOT / "data/sites.json").read_text(encoding="utf-8"))
done = b.load_details()
for r in b.load_rows():
    if r["year"] != year or not r["url"] or (todo and r["pid"] in done):
        continue
    s = sites.get(r["url"])
    if not s:
        print(f"## {r['pid']} {r['name']} -- not captured yet")
        continue
    t = (s.get("text") or "")[:260]
    print(f"## {r['pid']} {r['name']} [{s['status']}{' ' + str(s.get('httpStatus')) if s.get('httpStatus') else ''}] {s.get('error', '')}")
    if s.get("finalUrl") and s["finalUrl"].rstrip("/") != r["url"].rstrip("/"):
        print(f"-> {s['finalUrl'][:120]}")
    print(f"T: {s.get('title', '')[:120]} | D: {s.get('desc', '')[:200]}")
    print(f"X: {t}")
