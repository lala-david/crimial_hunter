# -*- coding: utf-8 -*-
"""모든 per-source CSV를 (chain,address)로 교차 집계해 마스터 생성.
source_count = 몇 개 독립 소스에 등장했는가 (품질/신뢰도 지표).
"""
import csv, os, re
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "sources")
DIR_OF = {"master_solana.csv": os.path.join(BASE, "solana"),
          "master_ethereum.csv": os.path.join(BASE, "ethereum"),
          "master_all.csv": BASE}

# (파일, 컬럼매핑) — 표준스키마는 None
# 매핑: address,chain,category,source,label,detail,ref_date 로 정규화
FILES = [
    ("chainabuse_crawl_SOL.csv", None),
    ("chainabuse_crawl_ETH.csv", None),
    ("solrpds_rugpull_sol.csv", None),
    ("scamsniffer_phishing_eth.csv", None),
    ("mew_darklist_eth.csv", None),
    ("forta_eth_malicious.csv", None),
    ("chainpatrol_blocked.csv", None),
    ("allenhark_sol.csv", None),
    ("solphishhunter_sol.csv", None),
    ("ethlabels_phishhack.csv", None),
    ("ethlabels_malicious.csv", None),
    ("cryptoscamdb_eth.csv", None),
    ("yuanqi_eth.csv", None),
    ("ptxphish_eth.csv", None),
    ("graphsense_eth.csv", None),
    ("graphsense_sol.csv", None),
    ("etherscan_blocked_eth.csv", None),
    ("silent_killer_sol.csv", None),
    ("midsummer_wash_sol.csv", None),
    ("tayvano_lazarus.csv", None),
    ("tayvano_trace_extra.csv", None),
    ("kismp_defihack.csv", None),
    ("stablecoin_blacklist_eth.csv", None),
    ("ransomwhere_crypto.csv", None),
    ("jp_mof_sanctions.csv", None),
    ("ofac_sanctions_all.csv", {"category": "category", "source": "source",
                                  "label": "programs", "detail": "entity_theme"}),
    ("gov_law_enforcement_all.csv", {"category": "category", "source": "source",
                                       "label": "jurisdiction", "detail": "detail"}),
]

def akey(a):
    return a.lower() if a.startswith("0x") else a

# 번주소·프리컴파일 — 소스 노이즈로 유입돼 교차확인처럼 보일 수 있어 제외
BURN = {"0x" + "0" * 40, "0x000000000000000000000000000000000000dead"} \
     | {f"0x{'0'*39}{i}" for i in "123456789abcdef"}

# agg[(chain, key)] = {...}
def _new():
    return {"categories": set(), "sources": set(),
            "labels": set(), "details": set(), "dates": set()}

agg = defaultdict(_new)
addr_of = {}   # (chain,key) -> 원본 주소 문자열

for fn, mp in FILES:
    p = os.path.join(SRC, fn)
    if not os.path.exists(p):
        print(f"  (건너뜀, 없음) {fn}")
        continue
    cnt = 0
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            addr = (r.get("address") or "").strip()
            chain = (r.get("chain") or "").strip()
            if not addr or chain not in ("SOL", "ETH"):
                continue
            if addr.lower() in BURN:
                continue
            cat = r.get(mp["category"]) if mp else r.get("category")
            src = r.get(mp["source"]) if mp else r.get("source")
            lbl = r.get(mp["label"]) if mp else r.get("label")
            det = r.get(mp["detail"]) if mp else r.get("detail")
            e = agg[(chain, akey(addr))]
            addr_of[(chain, akey(addr))] = addr
            if cat: e["categories"].add(cat.split(":")[0] if ":" in cat and cat.split(":")[0] in ("community_reported","chainabuse","sanctions") else cat)
            if src: e["sources"].add(src)
            if lbl: e["labels"].add(lbl[:40])
            if det: e["details"].add(det[:60])
            d = (r.get("ref_date") or "").strip()
            if d: e["dates"].add(d)
            cnt += 1
    print(f"  {fn}: {cnt} rows")

# 체인별로 분리 출력
def dump(chain, name):
    rows = []
    for (ch, key), e in agg.items():
        if ch != chain:
            continue
        rows.append([
            addr_of[(ch, key)], ch,
            len(e["sources"]),
            "|".join(sorted(e["sources"])),
            "|".join(sorted(e["categories"]))[:200],
            "|".join(sorted(e["labels"]))[:120],
            (max(e["dates"]) if e["dates"] else ""),
        ])
    rows.sort(key=lambda x: (-x[2], x[0]))   # source_count 내림차순
    with open(os.path.join(DIR_OF[name], name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "source_count", "sources", "categories", "labels", "ref_date"])
        w.writerows(rows)
    print(f"\n[{name}] {len(rows)}개 고유 주소")
    print(f"   source_count 분포: {dict(Counter(r[2] for r in rows))}")
    print(f"   소스별 등장: {dict(Counter(s for r in rows for s in r[3].split('|')))}")
    multi = [r for r in rows if r[2] >= 2]
    print(f"   2개 이상 소스 교차확인(고신뢰): {len(multi)}개")
    return rows

sol = dump("SOL", "master_solana.csv")
eth = dump("ETH", "master_ethereum.csv")

# 통합
with open(os.path.join(BASE, "master_all.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "source_count", "sources", "categories", "labels", "ref_date"])
    w.writerows(sol + eth)
print(f"\n[master_all.csv] 총 {len(sol)+len(eth)}개")
