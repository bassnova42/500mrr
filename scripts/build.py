"""从 data/projects.psv 生成 projects.csv 和 README.md。用法: python3 scripts/build.py"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THREADS = {
    2025: 46307973, 2024: 42373343, 2023: 38467691,
    2022: 34190421, 2021: 29667095, 2020: 24947167,
    2019: 20899863, 2018: 17790306, 2017: 15148804,
}

rows = []
with open(ROOT / "data/projects.psv", encoding="utf-8") as f:
    header = f.readline().strip().split("|")
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("|")
        assert len(parts) == len(header), line
        rows.append(dict(zip(header, parts)))

for r in rows:
    r["year"] = int(r["year"])
    r["hn_link"] = f"https://news.ycombinator.com/item?id={r['hn_id']}"

with open(ROOT / "projects.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["年份", "项目", "网址", "类别", "收入（作者自述）", "简介", "HN 评论"])
    for r in sorted(rows, key=lambda r: (-r["year"], r["category"], r["name"])):
        w.writerow([r["year"], r["name"], r["url"], r["category"], r["revenue"], r["desc"], r["hn_link"]])

import sys
sys.path.insert(0, str(ROOT / "scripts"))
import build_site
stats = build_site.main()
intro = (ROOT / "scripts/intro.md").read_text(encoding="utf-8")
years = sorted(THREADS)
est = [m for m in (build_site.monthly(r["revenue"]) for r in rows) if m is not None]
for k, v in {
    "N": len(rows), "UP": stats["up"], "NYEARS": len(years), "RANGE": f"{years[0]}–{years[-1]}",
    "EST": len(est), "PCT": round(100 * sum(500 <= m < 2000 for m in est) / len(est)),
    "TOPCATS": "、".join(f"{c}（{n}）" for c, n in Counter(r["category"] for r in rows).most_common(4)),
}.items():
    intro = intro.replace("{{" + k + "}}", str(v))

def esc(s):
    return s.replace("|", "/")

out = [intro.rstrip(), ""]
by_year = Counter(r["year"] for r in rows)
by_cat = Counter(r["category"] for r in rows)
out += ["## 数据概览", "", "| 年份 | 收录项目数 | 原帖 |", "|---|---|---|"]
for y in sorted(THREADS, reverse=True):
    out.append(f"| {y} | {by_year[y]} | [HN 原帖](https://news.ycombinator.com/item?id={THREADS[y]}) |")
out += ["", f"共 **{len(rows)}** 条。按类别：", "", "| 类别 | 数量 |", "|---|---|"]
for c, n in by_cat.most_common():
    out.append(f"| {c} | {n} |")
out.append("")

grouped = defaultdict(lambda: defaultdict(list))
for r in rows:
    grouped[r["year"]][r["category"]].append(r)
cat_order = [c for c, _ in by_cat.most_common()]
for y in sorted(grouped, reverse=True):
    out += [f"## {y} 年（{by_year[y]} 个）", ""]
    for c in cat_order:
        items = grouped[y].get(c)
        if not items:
            continue
        out += [f"### {c}", "", "| 项目 | 收入（自述） | 简介 |", "|---|---|---|"]
        for r in sorted(items, key=lambda r: r["name"].lower()):
            name = f"[{esc(r['name'])}]({r['url']})" if r["url"] else esc(r["name"])
            desc = esc(r["desc"]) if r["desc"] not in ("", "—") else ""
            out.append(f"| {name} | {esc(r['revenue'])} | {desc} [↗]({r['hn_link']}) |")
        out.append("")

out.append((ROOT / "scripts/deploy.md").read_text(encoding="utf-8"))
(ROOT / "README.md").write_text("\n".join(out), encoding="utf-8")

import json
(ROOT / "site").mkdir(exist_ok=True)
print(f"{len(rows)} rows -> projects.csv, README.md")
