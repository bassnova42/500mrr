"""Build the local site: site/index.html (screenshot grid) and site/p/<pid>.html (one page per project).

Inputs:
  data/projects.psv  projects (year|hn_id|name|url|category|revenue|desc)
  data/sites.json    screenshot + liveness results from tools/capture.js
  data/details.psv   pid|summary|money|status  (written by hand; status is optional override)
Usage: python3 scripts/build_site.py
"""
import html
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700'
         '&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">')
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
    (SITE / "p").mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(order):
        label, cls = STATUS.get(r["status"], STATUS["unclear"])
        s = r["site"]
        if r["shot"]:
            shot = f'<a href="../{e(r["shot"])}" target="_blank" rel="noopener"><img src="../{e(r["shot"])}" alt="{e(r["name"])} 网站截图"></a>'
        elif r["status"] == "hijacked":
            msg = "这个域名现在被博彩或其他无关网站占用，所以不显示截图。"
        else:
            msg = "原评论没有给出网址，所以没有截图。" if not r["url"] else "没能截到图：" + e(s.get("note") or s.get("error") or "网站没有响应")
        if not r["shot"]:
            shot = f'<div class="ph">{msg}</div>'
        checked = s.get("checkedAt", "")[:10]
        final = s.get("finalUrl") or ""
        redirect = f'<dd>跳转到 <a href="{e(final)}" target="_blank" rel="noopener">{e(final)}</a></dd>' if final and final.rstrip("/") != r["url"].rstrip("/") else ""
        facts = [
            ("状态", f'<span class="status {cls}">{label}</span>' + (f'<span style="color:var(--muted)">（{checked} 检查{"，" + e(s["note"]) if s.get("note") else ""}）</span>' if checked else "")),
            ("年份", f'{e(r["year"])} 年帖子'),
            ("类别", e(r["category"])),
            ("收入（自述）", f'<span class="money">{e(r["revenue"])}</span>'),
        ]
        if r["url"]:
            facts.append(("网址", f'<a href="{e(r["url"])}" target="_blank" rel="noopener">{e(r["url"])}</a>'))
        facts_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts)
        if redirect:
            facts_html += "<dt></dt>" + redirect
        site_meta = ""
        if s.get("title") or s.get("desc"):
            site_meta = f'<div>网站标题：{e(s.get("title", ""))}</div>' + (f'<div>网站描述：{e(s.get("desc", ""))}</div>' if s.get("desc") else "")
        money = f'<h2>怎么挣钱</h2><p>{e(r["money"])}</p>' if r["money"] else ""
        prev_r, next_r = order[i - 1] if i else None, order[i + 1] if i + 1 < len(order) else None
        pager = '<nav class="pager">' + (f'<a href="{prev_r["pid"]}.html">← {e(prev_r["name"])}</a>' if prev_r else "<span></span>") + \
                (f'<a href="{next_r["pid"]}.html">{e(next_r["name"])} →</a>' if next_r else "<span></span>") + "</nav>"
        body = f'''<div class="wrap">
<div class="crumb"><a href="../index.html">← 返回全部项目</a></div>
<article class="detail">
  <div class="shot">{shot}</div>
  <div>
    <div class="eyebrow">{e(r["year"])} · {e(r["category"])}</div>
    <h1>{e(r["name"])}</h1>
    <dl class="facts">{facts_html}</dl>
    <h2>简介</h2><p>{e(r["summary"])}</p>
    {money}
    {f'<a class="visit" href="{e(r["url"])}" target="_blank" rel="noopener">访问网站 ↗</a>' if r["url"] else ""}
    <div class="source">
      <div>来源：<a href="https://news.ycombinator.com/item?id={e(r["hn_id"])}" target="_blank" rel="noopener">作者在 HN 上的原评论 ↗</a></div>
      {site_meta}
    </div>
  </div>
</article>
{pager}
</div>'''
        (SITE / "p" / f'{r["pid"]}.html').write_text(page(f'{r["name"]} · 500MRR', body, 1), encoding="utf-8")

    data = [{
        "pid": r["pid"], "year": int(r["year"]), "name": r["name"], "category": r["category"], "revenue": r["revenue"],
        "summary": r["summary"], "money": r["money"], "status": r["status"], "thumb": r["thumb"], "url": r["url"],
    } for r in order]
    tpl = (ROOT / "scripts/gallery.template.html").read_text(encoding="utf-8")
    body = tpl.replace("/*DATA*/[]", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")) \
              .replace("/*STATUS*/{}", json.dumps({k: list(v) for k, v in STATUS.items()}, ensure_ascii=False))
    (SITE / "index.html").write_text(page("HN 月入 $500 副业名录", body), encoding="utf-8")
    # artifact.html: one-page version for claude.ai (gallery + hash-routed detail view, no document skeleton).
    adata = [dict(x, hn_id=r["hn_id"], checked=r["site"].get("checkedAt", "")[:10], note=r["site"].get("note", ""),
                  final=(r["site"].get("finalUrl") or "") if (r["site"].get("finalUrl") or "").rstrip("/") != r["url"].rstrip("/") else "",
                  stitle=r["site"].get("title", ""), sdesc=r["site"].get("desc", ""))
             for x, r in zip(data, order)]
    checked = max((r["site"].get("checkedAt", "")[:10] for r in rows), default="")
    atpl = (ROOT / "scripts/artifact.template.html").read_text(encoding="utf-8")
    apage = atpl.replace("/*CSS*/", (SITE / "assets/style.css").read_text(encoding="utf-8")) \
                .replace("/*CHECKED*/", checked) \
                .replace("/*DATA*/[]", json.dumps(adata, ensure_ascii=False).replace("</", "<\\/")) \
                .replace("/*STATUS*/{}", json.dumps({k: list(v) for k, v in STATUS.items()}, ensure_ascii=False))
    (SITE / "artifact.html").write_text(apage, encoding="utf-8")
    c = Counter(r["status"] for r in rows)
    print(f"{len(rows)} pages; status {dict(c)}; with details {sum(1 for r in rows if r['money'])}")


if __name__ == "__main__":
    main()
