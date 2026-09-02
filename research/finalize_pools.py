# -*- coding: utf-8 -*-
"""풀 검증 결과 종합 → 최종 카테고리 + 스캠코인 mint 역추출.
- 오탐(정상 대형 풀) 식별
- 풀 → 실제 스캠 코인 mint 매핑 (중복 제거: 한 코인의 여러 풀)
- 최종 정제된 솔라나 러그 데이터 통계
"""
import csv, os
from collections import Counter

D = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(D)
vd = list(csv.DictReader(open(os.path.join(D, "pool_verdict.csv"), encoding="utf-8")))
scan = {r["address"]: r for r in csv.DictReader(open(os.path.join(D, "sol_onchain_scan.csv"), encoding="utf-8"))}
toks = list(csv.DictReader(open(os.path.join(BASE, "solana", "master_solana_tokens.csv"), encoding="utf-8")))

n = len(vd)
print(f"=== 풀 검증 결과 종합 (검증 풀 {n}) ===\n")
verdicts = Counter(r["verdict"] for r in vd)
for k, v in verdicts.most_common():
    print(f"   {v:7} ({100*v/n:5.1f}%)  {k}")

# 유동성 분포 (active/false_positive)
def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0
liq_active = [f(r["liquidity_usd"]) for r in vd if r["verdict"] == "scam_pool_active"]
fp = [r for r in vd if r["verdict"] == "false_positive_major"]
print(f"\n[오탐(정상 대형 풀): {len(fp)}개]")
for r in sorted(fp, key=lambda x: -f(x["liquidity_usd"]))[:8]:
    print(f"   {r['pool'][:14]}.. 유동성 ${f(r['liquidity_usd']):,.0f} quote={r.get('quote_sym')} ({r.get('dex')})")

# 스캠 코인 mint 역추출 (풀 → 코인, 중복 제거)
scam_mints = Counter()
for r in vd:
    if r["verdict"] in ("scam_pool_active", "rug_completed") and r.get("scam_mint"):
        scam_mints[r["scam_mint"]] += 1
print(f"\n[풀 → 스캠 코인 mint 역추출]")
print(f"   유니크 스캠 코인: {len(scam_mints)}")
print(f"   한 코인당 평균 풀 수: {sum(scam_mints.values())/max(len(scam_mints),1):.2f}")
multi = sum(1 for c in scam_mints.values() if c >= 2)
print(f"   여러 풀 가진 코인(다중상장): {multi}")

# rug_completed 중 scam_mint 없는 것(=애초에 pair아님/토큰) 구분
rug_no_mint = sum(1 for r in vd if r["verdict"] == "rug_completed" and not r.get("scam_mint"))
print(f"\n[분류 정밀화]")
print(f"   러그완료(코인식별됨): {sum(1 for r in vd if r['verdict']=='rug_completed' and r.get('scam_mint'))}")
print(f"   러그완료(무응답, 코인미상): {rug_no_mint}")
print(f"   유동성남은 스캠풀: {len(liq_active)}")
print(f"   오탐 정상풀: {len(fp)}")

# 최종 정제 카테고리
print(f"\n[★ 최종 정제 카테고리]")
mints_in_toks = sum(1 for t in toks if scan.get(t['address'], {}).get('acct_type') == 'mint')
print(f"   원본 토큰파일: {len(toks)}")
print(f"   ├ 직접 토큰 mint: {mints_in_toks}")
print(f"   ├ 풀 주소(검증됨): {n}")
print(f"   │  ├ 러그 확정(유동성제거): {verdicts.get('rug_completed',0)}")
print(f"   │  ├ 유동성남은 스캠풀: {verdicts.get('scam_pool_active',0)}")
print(f"   │  └ 오탐(정상풀, 제거대상): {verdicts.get('false_positive_major',0)}")
print(f"   → 풀에서 역추출한 유니크 스캠코인: {len(scam_mints)}")

# 정제 결과 저장: 오탐 풀 주소 리스트 + 스캠코인 mint 리스트
with open(os.path.join(D, "false_positive_pools.txt"), "w", encoding="utf-8") as fo:
    fo.write("\n".join(r["pool"] for r in fp))
with open(os.path.join(D, "scam_mints_from_pools.txt"), "w", encoding="utf-8") as fo:
    fo.write("\n".join(sorted(scam_mints)))
print(f"\n저장: false_positive_pools.txt ({len(fp)}), scam_mints_from_pools.txt ({len(scam_mints)})")
