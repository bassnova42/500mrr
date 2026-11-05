"""Refine site status after capture: DNS check for unreachable sites, flag domains taken over by gambling/parking pages.
Usage: python3 tools/postcheck.py"""
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

P = Path(__file__).resolve().parent.parent / "data/sites.json"
sites = json.loads(P.read_text(encoding="utf-8"))
HIJACK = re.compile(r"casino|baccarat|slot gacor|\bjudi\b|togel|jun88|\bbandar\b|taruhan|nhà cái|cá cược|bắn cá|บาคาร่า|สล็อต|koko5000|\bbet\d{2,}|sportsbook bonus|vit1688", re.I)
PARKED = re.compile(r"forsale\.|/forsale/|parkedpages|domain is for sale|buy this domain|default server vhost|under construction|site in the making", re.I)

def resolves(host):
    try:
        socket.getaddrinfo(host, 443)
        return True
    except socket.gaierror:
        return False

for url, s in sites.items():
    host = urlparse(url).hostname or ""
    hay = " ".join([s.get("title", ""), s.get("desc", ""), s.get("text", "")[:400], s.get("finalUrl", "")])
    s["note"] = ""
    if s["status"] in ("unreachable", "dead") and s.get("error"):
        if not resolves(host):
            s["status"], s["note"] = "dead", "域名已无法解析"
        else:
            s["note"] = "域名还在，但网站没有响应"
    final_host = urlparse(s.get("finalUrl") or url).hostname or ""
    if HIJACK.search(hay):
        s["status"], s["note"] = "hijacked", "域名已被博彩等无关网站占用"
    elif PARKED.search(hay):
        s["status"], s["note"] = "dead", "域名待售、停放或只剩占位页"
    elif final_host and host and final_host.split(".")[-2:] != host.split(".")[-2:] and s["status"] == "up":
        s["note"] = f"跳转到 {final_host}"
tmp = P.with_suffix(".json.tmp")
tmp.write_text(json.dumps(sites, ensure_ascii=True, indent=1), encoding="utf-8")
tmp.replace(P)
from collections import Counter
print(Counter(s["status"] for s in sites.values()))
