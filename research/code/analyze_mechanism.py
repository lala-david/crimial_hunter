# -*- coding: utf-8 -*-
"""러그풀 메커니즘 유형 분류 — 우리 러그 토큰 온체인 특징을 리서치 5유형에 매핑.
유형: 무한발행 / 허니팟 / 개발자독점(선보유) / 유동성인출가능(하드러그) / 인사이더번들
"""
import csv, os, sys

path = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "mechanism_features.csv")
rows = [r for r in csv.DictReader(open(path, encoding="utf-8")) if r["status"] == "ok"]

def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

n = len(rows)
print(f"=== 러그 메커니즘 유형 분석 (유효 {n}건) ===\n")

# 각 유형 판정 (리서치 정의 → 우리 필드)
counts = {
    "무한발행 가능 (mint authority 미포기)": 0,
    "허니팟 가능 (freeze authority 미포기)": 0,
    "허니팟 (transfer fee >= 50%)": 0,
    "개발자 독점 (top1 >= 90%)": 0,
    "소수 독점 (top10 >= 90%)": 0,
    "유동성 인출가능 (LP 잠금 < 50% & 유동성 존재)": 0,
    "유동성 없음 (< $100)": 0,
    "인사이더 네트워크 탐지": 0,
    "creator 재범 (5개+ 토큰)": 0,
}
for r in rows:
    if r["mint_auth"] == "1":
        counts["무한발행 가능 (mint authority 미포기)"] += 1
    if r["freeze_auth"] == "1":
        counts["허니팟 가능 (freeze authority 미포기)"] += 1
    if (f(r["transfer_fee_pct"]) or 0) >= 50:
        counts["허니팟 (transfer fee >= 50%)"] += 1
    if (f(r["top1_pct"]) or 0) >= 90:
        counts["개발자 독점 (top1 >= 90%)"] += 1
    if (f(r["top10_pct"]) or 0) >= 90:
        counts["소수 독점 (top10 >= 90%)"] += 1
    lp = f(r["lp_locked_pct"]) or 0
    lq = f(r["liquidity_usd"]) or 0
    if lp < 50 and lq >= 100:
        counts["유동성 인출가능 (LP 잠금 < 50% & 유동성 존재)"] += 1
    if lq < 100:
        counts["유동성 없음 (< $100)"] += 1
    if r["insiders"] == "1":
        counts["인사이더 네트워크 탐지"] += 1
    if (f(r["creator_rug_count"]) or 0) >= 5:
        counts["creator 재범 (5개+ 토큰)"] += 1

print("[메커니즘 시그널 출현율]")
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"   {100*v/n:5.1f}%  {k}  ({v})")

# 권한 포기 여부 (요즘 러그 = 권한 없앰 가설 검증)
mint_off = sum(1 for r in rows if r["mint_auth"] == "0")
freeze_off = sum(1 for r in rows if r["freeze_auth"] == "0")
print(f"\n[권한 포기율] mint 포기 {100*mint_off/n:.1f}% / freeze 포기 {100*freeze_off/n:.1f}%")
print("  → 포기율 높으면 '요즘 러그는 권한남용(유형B)보다 선보유덤프(유형A)' 가설 지지")

# 유형 조합 (주 메커니즘 판별)
print("\n[주 메커니즘 분류 — 우선순위 배타 분류]")
primary = {"무한발행": 0, "허니팟": 0, "개발자독점덤프": 0, "유동성인출": 0, "인사이더": 0, "기타/저유동성": 0}
for r in rows:
    if r["mint_auth"] == "1":
        primary["무한발행"] += 1
    elif r["freeze_auth"] == "1" or (f(r["transfer_fee_pct"]) or 0) >= 50:
        primary["허니팟"] += 1
    elif (f(r["top1_pct"]) or 0) >= 80:
        primary["개발자독점덤프"] += 1
    elif (f(r["lp_locked_pct"]) or 0) < 50 and (f(r["liquidity_usd"]) or 0) >= 100:
        primary["유동성인출"] += 1
    elif r["insiders"] == "1":
        primary["인사이더"] += 1
    else:
        primary["기타/저유동성"] += 1
for k, v in sorted(primary.items(), key=lambda x: -x[1]):
    print(f"   {100*v/n:5.1f}%  {k}  ({v})")

# 위험태그 랭킹
from collections import Counter
risk = Counter(r["top_risk"] for r in rows if r["top_risk"])
print("\n[최상위 위험 태그]")
for name, c in risk.most_common(10):
    print(f"   {100*c/n:5.1f}%  {name}")
