# -*- coding: utf-8 -*-
"""크롤링한 chainabuse_reports_<chain>.jsonl을 주소 단위로 정규화한다.
report 1건 → 신고된 주소 N개로 폭발. 실제 scamCategory 부여.
"""
import csv, json, os, sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "processed")

CHAINS = sys.argv[1:] or ["SOL", "ETH"]

# Chainabuse ChainKind -> 우리 chain 코드
CHAIN_MAP = {"SOL": "SOL", "ETH": "ETH", "BTC": "BTC", "BINANCE": "BSC",
             "TRON": "TRON", "POLYGON": "POLYGON", "ARBITRUM": "ARB", "BASE": "BASE"}

def normalize(chain):
    rows = []          # address, chain, category, source, label, detail, ref_date
    path = os.path.join(RAW, f"chainabuse_reports_{chain}.jsonl")
    if not os.path.exists(path):
        print(f"[{chain}] 파일 없음: {path}")
        return rows
    cat_counter = Counter()
    n_reports = 0
    addr_cats = defaultdict(set)
    addr_meta = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            node = json.loads(line)
            n_reports += 1
            sc = node.get("scamCategory") or "OTHER"
            created = (node.get("createdAt") or "")[:10]
            checked = node.get("checked")
            votes = node.get("biDirectionalVoteCount")
            for a in node.get("addresses", []):
                addr = a.get("address")
                ch = a.get("chain")
                if not addr or ch != chain:
                    continue
                addr_cats[addr].add(sc)
                cat_counter[sc] += 1
                # 최신 신고일/라벨/투표수 보존
                m = addr_meta.get(addr, {"date": created, "label": a.get("label") or "",
                                          "votes": votes or 0, "checked": bool(checked)})
                if created and created > m["date"]:
                    m["date"] = created
                if a.get("label"):
                    m["label"] = a["label"]
                if votes and votes > m["votes"]:
                    m["votes"] = votes
                m["checked"] = m["checked"] or bool(checked)
                addr_meta[addr] = m
    code = CHAIN_MAP.get(chain, chain)
    for addr, cats in addr_cats.items():
        m = addr_meta[addr]
        cat = "chainabuse:" + "+".join(sorted(cats))
        detail = f"votes={m['votes']};checked={m['checked']}"
        if m["label"]:
            detail = f"label={m['label']};" + detail
        rows.append([addr, code, cat, "chainabuse_crawl", "|".join(sorted(cats)), detail, m["date"]])
    # 저장
    outp = os.path.join(OUT, f"chainabuse_crawl_{chain}.csv")
    with open(outp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writerows(rows)
    print(f"[{chain}] 신고 {n_reports}건 -> 고유 주소 {len(rows)}개  ({outp})")
    print(f"   카테고리 분포: {dict(cat_counter.most_common())}")
    return rows

# 마스터 병합은 build_master.py 담당 — 여기서는 per-source CSV 생성까지만.
for ch in CHAINS:
    normalize(ch)
