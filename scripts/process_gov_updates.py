# -*- coding: utf-8 -*-
"""정부·제재 라이브 갱신 — ① OFAC(0xB10C 미러, 매일 갱신) 신규 주소를
ofac_sanctions_all.csv에 증분 추가 ② Ransomwhere(랜섬웨어 지급주소) 정규화.
"""
import csv, json, os, re, urllib.request
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "processed")

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def cls(a):
    if re.match(r"^0x[0-9a-fA-F]{40}$", a): return "ETH"
    if a.startswith(("1", "3", "bc1")): return "BTC"
    if a.startswith("T") and len(a) == 34: return "TRON"
    if re.match(r"^[1-9A-HJ-NP-Za-km-z]{42,44}$", a): return "SOL"
    return "OTHER"

# ---- ① OFAC (0xB10C) ----
B10C = "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists"
ofac_new = {}   # addr -> chain
for cur, chain in (("ETH", "ETH"), ("SOL", "SOL"), ("USDT", "ETH"), ("USDC", "ETH")):
    try:
        addrs = json.loads(fetch(f"{B10C}/sanctioned_addresses_{cur}.json").decode())
        with open(os.path.join(RAW, f"ofac_{cur.lower()}.json"), "w", encoding="utf-8") as f:
            json.dump(addrs, f, indent=2)
        for a in addrs:
            a = a.strip()
            if a and cls(a) in ("ETH", "SOL"):
                ofac_new.setdefault(a.lower() if a.startswith("0x") else a, cls(a))
        print(f"  OFAC {cur}: {len(addrs)}개")
    except Exception as e:
        print(f"  (OFAC {cur} 실패: {e})")

ofac_path = os.path.join(OUT, "ofac_sanctions_all.csv")
existing_rows = list(csv.DictReader(open(ofac_path, encoding="utf-8")))
have = {(r["address"].lower() if r["address"].startswith("0x") else r["address"]) for r in existing_rows}
fields = existing_rows[0].keys() if existing_rows else \
    ["address", "chain", "category", "source", "programs", "entity_theme", "ref_date"]
added = 0
with open(ofac_path, "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(fields))
    for a, chain in sorted(ofac_new.items()):
        if a in have:
            continue
        row = {k: "" for k in fields}
        row.update({"address": a, "chain": chain, "category": "sanctions", "source": "ofac_sdn"})
        w.writerow(row)
        added += 1
print(f"-> ofac_sanctions_all.csv: 신규 {added}개 추가 (기존 {len(existing_rows)})")

# ---- ② Ransomwhere ----
try:
    data = fetch("https://data.opensanctions.org/datasets/latest/ransomwhere/targets.simple.csv")
    with open(os.path.join(RAW, "opensanctions_ransomwhere.csv"), "wb") as f:
        f.write(data)
    print(f"  ransomwhere 재다운로드: {len(data):,}B")
except Exception as e:
    print(f"  (ransomwhere 재다운로드 실패, 기존 raw 사용: {e})")

# OpenSanctions CryptoWallet 스키마: 주소가 name 컬럼에 있음 (jp_mof와 동일)
rows = []
seen = set()
with open(os.path.join(RAW, "opensanctions_ransomwhere.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r.get("schema") != "CryptoWallet":
            continue
        a = (r.get("name") or "").strip()
        ch = cls(a)
        if not a or ch not in ("ETH", "SOL"):
            continue
        key = a.lower() if a.startswith("0x") else a
        if key in seen:
            continue
        seen.add(key)
        day = (r.get("last_seen") or "")[:10]
        rows.append([key if ch == "ETH" else a, ch, "ransomware", "ransomwhere",
                     "ransomware payment", (r.get("aliases") or "")[:60], day])
with open(os.path.join(OUT, "ransomwhere_crypto.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(rows)
print(f"-> ransomwhere_crypto.csv: {len(rows)}개  {dict(Counter(r[1] for r in rows))}")
