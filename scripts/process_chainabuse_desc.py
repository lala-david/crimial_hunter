# -*- coding: utf-8 -*-
"""Chainabuse 신고 '본문(description)'에서 주소 추출 — 태그된 주소 외에
본문에 언급된 collector·cash-out 지갑을 캔다. (SOL은 기존에 수행, ETH는 신규)
출력: sources/chainabuse_desc_eth.csv / chainabuse_desc_sol.csv
"""
import csv, json, os, re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "sources")

ETH_RE = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
SOL_RE = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])")

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
IDX = {c: i for i, c in enumerate(ALPH)}

def valid_sol(s):
    n = 0
    for c in s:
        if c not in IDX:
            return False
        n = n * 58 + IDX[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return len(b"\x00" * (len(s) - len(s.lstrip("1"))) + body) == 32

found = {"ETH": {}, "SOL": {}}   # addr -> (category, date)
stats = Counter()

for fname in ("chainabuse_reports_SOL.jsonl", "chainabuse_reports_ETH.jsonl"):
    p = os.path.join(RAW, fname)
    if not os.path.exists(p):
        continue
    with open(p, encoding="utf-8") as f:
        for line in f:
            node = json.loads(line)
            desc = node.get("description") or ""
            if len(desc) < 20:
                continue
            tagged = {(a.get("address") or "").lower() for a in node.get("addresses", [])}
            tagged |= {a.get("address") or "" for a in node.get("addresses", [])}
            cat = node.get("scamCategory") or "OTHER"
            day = (node.get("createdAt") or "")[:10]
            for m in ETH_RE.findall(desc):
                a = m.lower()
                if a not in tagged and a not in found["ETH"]:
                    found["ETH"][a] = (cat, day)
                    stats["ETH_new"] += 1
            for m in SOL_RE.findall(desc):
                if m not in tagged and m not in found["SOL"] and valid_sol(m):
                    found["SOL"][m] = (cat, day)
                    stats["SOL_new"] += 1

for chain, name in (("ETH", "chainabuse_desc_eth.csv"), ("SOL", "chainabuse_desc_sol.csv")):
    rows = [[a, chain, "community_reported_desc", "chainabuse_desc",
             cat, "본문 언급 collector/cash-out", day]
            for a, (cat, day) in sorted(found[chain].items())]
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writerows(rows)
    print(f"-> {name}: {len(rows)}개")
print(f"통계: {dict(stats)}")
