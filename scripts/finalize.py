# -*- coding: utf-8 -*-
"""Chainabuse 카테고리 병합 + 최종 통합본/매니페스트 생성."""
import csv, json, os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "processed")

# ---------- Chainabuse enriched 카테고리를 master_solana에 병합 ----------
enr = {}
ep = os.path.join(OUT, "chainabuse_sol_enriched.csv")
if os.path.exists(ep):
    with open(ep, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("categories"):
                enr[r["address"]] = r["categories"].replace("|", "+")

def merge_categories(master_name):
    p = os.path.join(OUT, master_name)
    with open(p, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = 0
    for r in rows:
        if r["source"] == "chainabuse_sitemap" and r["address"] in enr:
            r["label"] = enr[r["address"]]
            r["category"] = "community_reported:" + enr[r["address"]]
            n += 1
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writeheader()
        w.writerows(rows)
    return rows, n

sol_rows, n_sol = merge_categories("master_solana.csv")
eth_rows, _ = merge_categories("master_ethereum.csv")
print(f"Chainabuse 카테고리 병합: SOL {n_sol}건")

# ---------- 통합 마스터 (SOL+ETH) ----------
combined = []
for r in sol_rows + eth_rows:
    combined.append(r)
with open(os.path.join(OUT, "master_all.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writeheader()
    w.writerows(combined)

# ---------- 매니페스트 ----------
def summarize(rows):
    return {
        "total": len(rows),
        "by_source": dict(Counter(r["source"] for r in rows)),
        "by_category": dict(Counter(r["category"].split(":")[0] for r in rows)),
    }

manifest = {
    "generated": "2026-08-26",
    "chains": {
        "solana": summarize(sol_rows),
        "ethereum": summarize(eth_rows),
    },
    "combined_total": len(combined),
}
with open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print(json.dumps(manifest, ensure_ascii=False, indent=2))
