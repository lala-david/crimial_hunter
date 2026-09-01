# -*- coding: utf-8 -*-
"""러그 vs 정상 토큰 특징 비교 → 조기감지 판별력.
각 특징에 대해 두 그룹의 분포를 비교하고, 단순 룰의 검출률(recall)/오탐(FPR)을 계산.
"""
import csv, os

D = os.path.dirname(os.path.abspath(__file__))

def load(name):
    rows = list(csv.DictReader(open(os.path.join(D, name), encoding="utf-8")))
    return [r for r in rows if r["status"] == "ok"]

rug = load("token_features.csv")
ctl = load("control_features.csv")
print(f"러그(스캠) {len(rug)}개  vs  정상 {len(ctl)}개\n")

def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def frac_ge(rows, key, thr):
    vals = [fnum(r[key]) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, 0
    return sum(1 for v in vals if v >= thr) / len(vals), len(vals)

def frac_true(rows, key):
    vals = [r[key] for r in rows if r[key] not in ("", None)]
    if not vals:
        return None, 0
    return sum(1 for v in vals if v == "1") / len(vals), len(vals)

def frac_le(rows, key, thr):
    vals = [fnum(r[key]) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, 0
    return sum(1 for v in vals if v <= thr) / len(vals), len(vals)

print("=" * 62)
print(f"{'룰 (이 조건이면 러그 의심)':38} {'러그검출':>8} {'정상오탐':>8}")
print("=" * 62)

def row(label, rf, cf):
    if rf is None or cf is None:
        print(f"{label:38} {'-':>8} {'-':>8}")
        return
    print(f"{label:38} {rf*100:7.1f}% {cf*100:7.1f}%")

for thr in (99, 95, 90, 80):
    r, _ = frac_ge(rug, "top1_pct", thr)
    c, _ = frac_ge(ctl, "top1_pct", thr)
    row(f"단일홀더 지분 >= {thr}%", r, c)
print()
for thr in (95, 90, 80):
    r, _ = frac_ge(rug, "top10_pct", thr)
    c, _ = frac_ge(ctl, "top10_pct", thr)
    row(f"상위10홀더 합산 >= {thr}%", r, c)
print()
for thr in (1, 100):
    r, _ = frac_le(rug, "liquidity_usd", thr)
    c, _ = frac_le(ctl, "liquidity_usd", thr)
    row(f"유동성 <= ${thr}", r, c)
print()
r, _ = frac_true(rug, "mint_auth_live"); c, _ = frac_true(ctl, "mint_auth_live")
row("발행권한 살아있음", r, c)
r, _ = frac_true(rug, "freeze_auth_live"); c, _ = frac_true(ctl, "freeze_auth_live")
row("동결권한 살아있음", r, c)
r, _ = frac_true(rug, "insiders_detected"); c, _ = frac_true(ctl, "insiders_detected")
row("인사이더 네트워크 탐지", r, c)

# 복합 룰: 단일홀더>=90% AND 유동성<=$100
def combo(rows):
    hit = 0
    n = 0
    for r in rows:
        t1 = fnum(r["top1_pct"]); lq = fnum(r["liquidity_usd"])
        if t1 is None or lq is None:
            continue
        n += 1
        if t1 >= 90 and lq <= 100:
            hit += 1
    return hit / n if n else None
print()
print("=" * 62)
rc, cc = combo(rug), combo(ctl)
row("복합: 단일홀더>=90% AND 유동성<=$100", rc, cc)
print("=" * 62)

# 스코어 분포
import statistics as st
for name, rows in (("러그", rug), ("정상", ctl)):
    sc = [v for v in (fnum(r["score"]) for r in rows) if v is not None]
    if sc:
        print(f"{name} RugCheck score: 중앙값 {st.median(sc):.0f}  평균 {st.mean(sc):.0f}")
