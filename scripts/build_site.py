"""Build the local site: site/index.html (screenshot grid) and site/p/<pid>.html (one page per project).

Inputs:
  data/projects.psv  projects (year|hn_id|name|url|category|revenue|desc)
  data/sites.json    screenshot + liveness results from tools/capture.js
  data/details.psv   pid|summary|money|status  (written by hand; status is optional override)
Usage: python3 scripts/build_site.py
"""
import html
import json
import re
import subprocess
from urllib.parse import urlparse
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700'
         '&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Noto+Sans+SC:wght@500;900&display=swap">')
STATUS = {  # key -> (label, css class)
    "up": ("在线", "up"),
    "blocked": ("有访问限制，可能在线", "warn"),
    "unclear": ("无法判断", "warn"),
    "unreachable": ("打不开", "dead"),
    "dead": ("疑似停运", "dead"),
    "hijacked": ("域名已易主", "dead"),
    "sold": ("已出售", "warn"),
    "closed": ("已关停", "dead"),
    "nourl": ("没有网址", "none"),
}
e = lambda s: html.escape(s or "", quote=True)


def load_rows():
    lines = (ROOT / "data/projects.psv").read_text(encoding="utf-8").strip().split("\n")
    header = lines[0].split("|")
    rows, seen = [], Counter()
    for line in lines[1:]:
        r = dict(zip(header, line.split("|")))
        seen[r["hn_id"]] += 1
        r["pid"] = r["hn_id"] if seen[r["hn_id"]] == 1 else f"{r['hn_id']}-{seen[r['hn_id']]}"
        rows.append(r)
    return rows


def load_details():
    p = ROOT / "data/details.psv"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip():
                continue
            parts = line.split("|")
            parts += [""] * (4 - len(parts))
            out[parts[0]] = {"summary": parts[1], "money": parts[2], "status": parts[3]}
    return out


def thumb(shot):
    """Make a 640px-wide thumbnail next to the screenshot (macOS sips)."""
    src = SITE / shot
    dst = SITE / "shots/thumb" / src.name
    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["sips", "-Z", "640", str(src), "--out", str(dst)], capture_output=True)
    return f"shots/thumb/{src.name}" if dst.exists() else None


def page(title, body, depth=0):
    pre = "../" * depth
    return ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'<title>{e(title)}</title>\n{FONTS}\n<link rel="stylesheet" href="{pre}assets/style.css">\n'
            f'</head>\n<body>\n{body}\n</body>\n</html>\n')


def main():
    rows = load_rows()
    sites = json.loads((ROOT / "data/sites.json").read_text(encoding="utf-8")) if (ROOT / "data/sites.json").exists() else {}
    details = load_details()

    for r in rows:
        s = sites.get(r["url"], {}) if r["url"] else {}
        d = details.get(r["pid"], {})
        r["site"] = s
        r["status"] = d.get("status") or (s.get("status") if r["url"] else "nourl") or "unclear"
        r["summary"] = d.get("summary") or r["desc"]
        r["money"] = d.get("money") or ""
        # A taken-over domain now shows someone else's (often gambling) page, so don't show that screenshot.
        hidden = r["status"] == "hijacked"
        r["shot"] = s.get("shot") if s.get("shot") and (SITE / s["shot"]).exists() and not hidden else None
        r["thumb"] = thumb(r["shot"]) if r["shot"] else None

    order = sorted(rows, key=lambda r: (-int(r["year"]), r["name"].lower()))
    checked = max((r["site"].get("checkedAt", "")[:10] for r in rows), default="")
    for r in order:
        r["m"] = monthly(r["revenue"])
        r["host"] = urlparse(r["url"]).hostname.removeprefix("www.") if r["url"] else ""

    (SITE / "p").mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(order):
        (SITE / "p" / f'{r["pid"]}.html').write_text(page(f'{r["name"]} · 500MRR', detail_html(r, i, order), 1), encoding="utf-8")

    data = [{
        "pid": r["pid"], "year": int(r["year"]), "name": r["name"], "category": r["category"], "revenue": r["revenue"],
        "summary": r["summary"], "money": r["money"], "status": r["status"], "thumb": r["thumb"], "url": r["url"],
        "hn_id": r["hn_id"], "checked": r["site"].get("checkedAt", "")[:10], "note": r["site"].get("note", ""),
        "final": final_url(r), "stitle": r["site"].get("title", ""), "sdesc": r["site"].get("desc", ""),
    } for r in order]
    by_name = {r["name"]: r for r in rows if r["status"] == "up"}
    hero = [by_name[n]["thumb"] for n in HERO_NAMES if n in by_name and by_name[n]["thumb"]]
    tpl = (ROOT / "scripts/gallery.template.html").read_text(encoding="utf-8")
    def fill(mode):
        return tpl.replace('/*MODE*/"site"', json.dumps(mode)) \
                  .replace("/*CHECKED*/", checked) \
                  .replace("/*HERO*/[]", json.dumps(hero)) \
                  .replace("/*DATA*/[]", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")) \
                  .replace("/*STATUS*/{}", json.dumps({k: list(v) for k, v in STATUS.items()}, ensure_ascii=False))
    (SITE / "index.html").write_text(page("HN 月入 $500 副业名录", fill("site")), encoding="utf-8")
    # artifact.html: one-page version for claude.ai (gallery + hash-routed detail view, no document skeleton).
    atpl = (ROOT / "scripts/artifact.template.html").read_text(encoding="utf-8")
    apage = atpl.replace("/*CSS*/", (SITE / "assets/style.css").read_text(encoding="utf-8")).replace("/*BODY*/", fill("artifact"))
    (SITE / "artifact.html").write_text(apage, encoding="utf-8")
    c = Counter(r["status"] for r in rows)
    print(f"{len(rows)} pages; status {dict(c)}; with details {sum(1 for r in rows if r['money'])}")


# Well-known projects whose screenshots make up the hero wall.
HERO_NAMES = ["OnlineOrNot", "Label LIVE", "BudgetSheet", "Online Solitaire", "webtoapp.design", "Formester",
              "Hacker Newsletter", "ChessCraft", "Stock Events", "FLX Websites", "SaaS Pegasus", "Filestash",
              "Tradytics", "Lightnote", "Vlad.studio", "ScreenMemory", "Canine", "CoPlay", "Escape Team", "PastMaps"]


def monthly(rev):
    """Same estimate as monthly() in gallery.template.html."""
    if re.search(r"累计|Kickstarter|首年|首月|以来|个月|3周|营收\$|\d+ ×", rev):
        return None
    m = re.search(r"[$€£]\s?([\d.,]+)\s*(k)?", rev, re.I)
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    if m.group(2):
        v *= 1000
    if re.search(r"年|ARR", rev) and "/月" not in rev:
        v /= 12
    elif "/周" in rev:
        v *= 4.3
    elif "/天" in rev:
        v *= 30
    elif "暑期" in rev:
        v /= 12
    return v


def money(v):
    if v >= 1000:
        s = f"{v / 1000:.0f}" if v >= 10000 else f"{v / 1000:.1f}".removesuffix(".0")
        return f"${s}k"
    return f"${round(v)}"


def final_url(r):
    f = r["site"].get("finalUrl") or ""
    return f if f and f.rstrip("/") != r["url"].rstrip("/") else ""


DEAD = {"dead", "unreachable", "closed", "hijacked"}


def card_html(r, pre):
    label, cls = STATUS.get(r["status"], STATUS["unclear"])
    img = f'<img src="{pre}{e(r["thumb"])}" alt="" loading="lazy">' if r["thumb"] else \
          f'<div class="ph"><div><b>{e(r["name"][:1])}</b>{"没有截图" if r["url"] else "没有网址"}</div></div>'
    badge = f'<span class="badge">{money(r["m"])}/月</span>' if r["m"] is not None else ""
    return (f'<li class="card{" is-dead" if r["status"] in DEAD else ""}"><a href="{e(r["pid"])}.html">'
            f'<div class="browser"><div class="chrome"><i></i><i></i><i></i><span>{e(r["host"] or "没有网址")}</span></div>'
            f'<div class="view">{img}{badge}</div></div>'
            f'<div class="ctitle">{e(r["name"])}</div>'
            f'<div class="cmeta"><span class="yr">{r["year"]}</span><span>{e(r["category"])}</span><span class="status {cls}">{label}</span></div>'
            f'<div class="csum">{e(r["summary"])}</div></a></li>')


def detail_html(r, i, order):
    label, cls = STATUS.get(r["status"], STATUS["unclear"])
    s = r["site"]
    ext = lambda href, text: f'<a href="{e(href)}" target="_blank" rel="noopener">{e(text)}</a>'
    if r["shot"]:
        shot = f'<a href="../{e(r["shot"])}" target="_blank" rel="noopener"><img src="../{e(r["shot"])}" alt="{e(r["name"])} 网站截图"></a>'
    elif r["status"] == "hijacked":
        shot = '<div class="ph">这个域名现在被博彩或其他无关网站占用，所以不显示截图。</div>'
    else:
        msg = "原评论没有给出网址，所以没有截图。" if not r["url"] else "没能截到图：" + e(s.get("note") or s.get("error") or "网站没有响应")
        shot = f'<div class="ph">{msg}</div>'
    checked = s.get("checkedAt", "")[:10]
    facts = f'<dt>状态</dt><dd><span class="status {cls}">{label}</span>' + \
        (f'<span style="color:var(--muted)">（{checked} 检查{"，" + e(s["note"]) if s.get("note") else ""}）</span>' if checked else "") + "</dd>" + \
        f'<dt>年份</dt><dd>{e(r["year"])} 年帖子</dd><dt>类别</dt><dd>{e(r["category"])}</dd>'
    if r["url"]:
        facts += f'<dt>网址</dt><dd>{ext(r["url"], r["url"])}</dd>'
    if final_url(r):
        facts += f'<dt>跳转</dt><dd>{ext(final_url(r), final_url(r))}</dd>'
    rel = sorted((x for x in order if x["category"] == r["category"] and x["pid"] != r["pid"] and x["thumb"] and x["status"] not in DEAD),
                 key=lambda x: -(x["m"] or -1))[:4]
    related = (f'<section class="related"><div class="sec-head"><div><div class="eyebrow">More like this</div><h2>同类项目</h2></div></div>'
               f'<ul class="rgrid">{"".join(card_html(x, "../") for x in rel)}</ul></section>') if rel else ""
    prev_r, next_r = order[i - 1] if i else None, order[i + 1] if i + 1 < len(order) else None
    pager = '<nav class="pager">' + (f'<a href="{prev_r["pid"]}.html">← {e(prev_r["name"])}</a>' if prev_r else "<span></span>") + \
            (f'<a href="{next_r["pid"]}.html">{e(next_r["name"])} →</a>' if next_r else "<span></span>") + "</nav>"
    bg = f'<div class="bgshot" style="background-image:url(\'../{e(r["thumb"])}\')"></div>' if r["thumb"] else ""
    return f"""<div class="dhero">{bg}<div class="bgfade"></div>
<div class="gutter"><div class="wrap">
<div class="crumb"><a href="../index.html">← 返回全部项目</a></div>
<article class="detail">
  <div class="browser"><div class="chrome"><i></i><i></i><i></i><span>{e(r["host"] or "没有网址")}</span></div><div class="view">{shot}</div></div>
  <div class="prose">
    <div class="eyebrow">{e(r["year"])} · {e(r["category"])}</div>
    <h1>{e(r["name"])}</h1>
    <div class="bigrev"><small>作者自述收入</small><b>{e(r["revenue"])}</b></div>
    <dl class="facts">{facts}</dl>
    <h2>简介</h2><p>{e(r["summary"])}</p>
    {f'<h2>怎么挣钱</h2><p>{e(r["money"])}</p>' if r["money"] else ""}
    {f'<a class="btn primary visit" href="{e(r["url"])}" target="_blank" rel="noopener">访问网站 ↗</a>' if r["url"] else ""}
    <div class="source">
      <div>来源：{ext("https://news.ycombinator.com/item?id=" + r["hn_id"], "作者在 HN 上的原评论 ↗")}</div>
      {f'<div>网站标题：{e(s["title"])}</div>' if s.get("title") else ""}
      {f'<div>网站描述：{e(s["desc"])}</div>' if s.get("desc") else ""}
    </div>
  </div>
</article>
</div></div></div>
<div class="gutter"><div class="wrap">{related}{pager}</div></div>"""


if __name__ == "__main__":
    main()
