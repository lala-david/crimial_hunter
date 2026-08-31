# -*- coding: utf-8 -*-
import csv, json, os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "processed")

def load(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return []
    return list(csv.DictReader(open(p, encoding="utf-8")))

def summ(rows):
    src = Counter(s for r in rows for s in r["sources"].split("|"))
    return {
        "unique_addresses": len(rows),
        "cross_confirmed_2plus": sum(1 for r in rows if int(r["source_count"]) >= 2),
        "by_source_appearance": dict(src.most_common()),
    }

sol = load("master_solana.csv")
eth = load("master_ethereum.csv")
sol_wallet = [r for r in sol if r["sources"] != "solrpds"]

manifest = {
    "generated": "2026-08-26",
    "note": "source_count>=2 는 여러 독립 소스에 중복 등장(고신뢰). SolRPDS 단독은 러그풀 풀/토큰(지갑 아님).",
    "solana": {
        **summ(sol),
        "real_scammer_wallets_excl_rugpull": len(sol_wallet),
        "solrpds_rugpull_only": len(sol) - len(sol_wallet),
    },
    "ethereum": summ(eth),
    "government_crypto_sanctions_sources": {
        "us_ofac_sdn": "1006 wallets (multi-chain, country-attributed)",
        "israel_nbctf": "1725 wallets (terrorism financing, mostly TRON)",
        "japan_mof": "26 wallets (BTC/ETH)",
        "verified_zero_crypto": ["EU", "UK(FCDO/OFSI)", "UN", "Ukraine", "Canada",
                                  "Australia", "Switzerland", "France", "Singapore"],
    },
    "total_unique": len(sol) + len(eth),
}
with open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(json.dumps(manifest, ensure_ascii=False, indent=2))
