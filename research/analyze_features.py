# -*- coding: utf-8 -*-
"""수집된 러그풀 특징 분포 분석 → 조기감지 시그널 프로파일.
사용법: python analyze_features.py [token_features.csv]
"""
import csv, os, sys
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_features.csv")
rows = list(csv.DictReader(open(path, encoding="utf-8")))
ok = [r for r in rows if r["status"] == "ok"]

def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def pct_true(key):
    vals = [r[key] for r in ok if r[key] not in ("", None)]
    n = sum(1 for v in vals if v == "1")
    return n, len(vals)

def dist(key, buckets):
    c = Counter()
    for r in ok:
        v = fnum(r[key])
        if v is None:
            continue
        for lo, hi, lab in buckets:
            if lo <= v < hi:
                c[lab] += 1
                break
    return c

print(f"=== 러그풀 특징 분석 (유효 응답 {len(ok)} / 전체 {len(rows)}) ===\n")

st = Counter(r["status"] for r in rows)
print(f"[응답 상태] {dict(st)}")
closed = st.get("invalid_or_closed", 0)
print(f"  → 이미 rug 완료(계정 닫힘) 추정: {closed} ({100*closed/max(len(rows),1):.0f}%)\n")

# 권한 생존
for key, lab in (("mint_auth_live", "발행권한(mintAuthority) 살아있음 = 무한발행 가능"),
                 ("freeze_auth_live", "동결권한(freezeAuthority) 살아있음 = 허니팟 가능")):
    n, tot = pct_true(key)
    if tot:
        print(f"[{lab}] {n}/{tot} = {100*n/tot:.1f}%")
print()

# 홀더 집중도
print("[최대 단일홀더 지분 top1_pct]")
for lab, cnt in dist("top1_pct", [(0,10,"<10%"),(10,30,"10-30%"),(30,50,"30-50%"),
                                   (50,80,"50-80%"),(80,95,"80-95%"),(95,100.01,"95%+")]).most_common():
    print(f"   {lab:8} {cnt}")
print("\n[상위10홀더 합산 top10_pct]")
for lab, cnt in dist("top10_pct", [(0,30,"<30%"),(30,50,"30-50%"),(50,70,"50-70%"),
                                    (70,90,"70-90%"),(90,100.01,"90%+")]).most_common():
    print(f"   {lab:8} {cnt}")

# 유동성 / LP
print("\n[유동성 liquidity_usd]")
for lab, cnt in dist("liquidity_usd", [(0,0.01,"$0"),(0.01,100,"<$100"),(100,1000,"$100-1k"),
                                        (1000,1e12,"$1k+")]).most_common():
    print(f"   {lab:8} {cnt}")

# creator 재범
print("\n[creator가 만든 토큰 수 creator_tokens]")
for lab, cnt in dist("creator_tokens", [(0,2,"1개(단발)"),(2,6,"2-5개"),(6,20,"6-19개"),
                                         (20,1e9,"20개+(대량생산)")]).most_common():
    print(f"   {lab:8} {cnt}")

n, tot = pct_true("insiders_detected")
if tot:
    print(f"\n[인사이더 네트워크 탐지] {n}/{tot} = {100*n/tot:.1f}%")

# 위험 태그 랭킹
print("\n[가장 흔한 위험 태그 Top 15]")
risk = Counter()
for r in ok:
    for x in (r["risks"] or "").split("|"):
        if x:
            risk[x] += 1
for name, cnt in risk.most_common(15):
    print(f"   {100*cnt/max(len(ok),1):5.1f}%  {name}")

# 발행 플랫폼
print("\n[발행 플랫폼]")
for name, cnt in Counter(r["launchpad"] for r in ok if r["launchpad"]).most_common(8):
    print(f"   {cnt:4}  {name}")
