# -*- coding: utf-8 -*-
"""dawsbot/eth-labels v1 (accounts.csv) 정규화 — 악성 라벨만 추출.
입력: raw/ethlabels_accounts.csv (address,chainId,label,nameTag)
출력: processed/ethlabels_malicious.csv (표준 스키마, ETH만)
- 제외: blocked(번주소·프리컴파일 혼입), fraud-proof(롤업 정상 컨트랙트)
- take-action = Etherscan 피싱 경고 배너 라벨
"""
import csv, os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "processed")

CATEGORY = {
    "take-action": "phishing",
    "phish-hack": "phishing",
    "heist": "exploit",
    "scam": "scam",
    "ofac-sanctions-lists": "sanctions",
    "ofac-sanctioned": "sanctions",
}

def category_of(label):
    if label in CATEGORY:
        return CATEGORY[label]
    if label == "exploit" or label.endswith("-exploit"):
        return "exploit"
    return None

seen = set()
rows = []
other_chains = Counter()
with open(os.path.join(RAW, "ethlabels_accounts.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        label = (r.get("label") or "").strip()
        cat = category_of(label)
        if not cat:
            continue
        a = (r.get("address") or "").strip().lower()
        if not a.startswith("0x") or len(a) != 42:
            continue
        if r.get("chainId") != "1":
            other_chains[r.get("chainId")] += 1
            continue
        if (a, label) in seen:
            continue
        seen.add((a, label))
        tag = (r.get("nameTag") or "").strip()
        if tag.lower() == "null":
            tag = ""
        rows.append([a, "ETH", cat, "eth_labels_dawsbot", label, tag[:60], ""])

with open(os.path.join(OUT, "ethlabels_malicious.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(rows)

uniq = len({r[0] for r in rows})
print(f"-> ethlabels_malicious.csv: {len(rows)} rows / 고유주소 {uniq}")
print(f"   라벨: {dict(Counter(r[4] for r in rows))}")
print(f"   카테고리: {dict(Counter(r[2] for r in rows))}")
if other_chains:
    print(f"   (타체인 악성 제외분: {dict(other_chains)})")
