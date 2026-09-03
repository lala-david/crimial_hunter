# -*- coding: utf-8 -*-
"""실험 감사 — 데이터/정제/스케일링/설계가 처음부터 맞는지 진단.
핵심 의심: (1) 라벨 정확성 (2) 출처 편향 (러그=RugCheck vs 정상=Jupiter) (3) 분포/이상치 (4) 다중공선성.
"""
import csv, os
import numpy as np

D = os.path.dirname(os.path.abspath(__file__))
FEATS = ["mint_auth_live", "freeze_auth_live", "top1_pct", "top10_pct",
         "total_holders", "lp_providers", "liquidity_usd"]

def load(name, label):
    out = []
    for r in csv.DictReader(open(os.path.join(D, "..", "data", name), encoding="utf-8")):
        if r["status"] != "ok":
            continue
        out.append((r, label))
    return out

data = load("token_features.csv", 1) + load("control_features.csv", 0)
y = np.array([d[1] for d in data])
raw = {}
miss = {}
for f in FEATS:
    col = []
    m = 0
    for r, _ in data:
        v = r.get(f, "")
        try:
            col.append(float(v))
        except (TypeError, ValueError):
            col.append(np.nan); m += 1
    raw[f] = np.array(col)
    miss[f] = m
n = len(data)
print(f"=== 감사: 러그 {int((y==1).sum())} / 정상 {int((y==0).sum())} (불균형 {(y==1).sum()/(y==0).sum():.1f}:1) ===\n")

# 1) 결측
print("[1] 결측률")
for f in FEATS:
    print(f"   {f:16} {100*miss[f]/n:5.1f}%")

# 2) 분포 (러그 vs 정상) + 이상치
print("\n[2] 분포 (러그 median / 정상 median / 최대값 — 스케일 편차)")
for f in FEATS:
    v = raw[f]
    rv, lv = v[y == 1], v[y == 0]
    rv, lv = rv[~np.isnan(rv)], lv[~np.isnan(lv)]
    print(f"   {f:16} 러그 {np.median(rv):12.2f} / 정상 {np.median(lv):12.2f} / max {np.nanmax(v):14.1f}")

# 3) 단일 feature 판별력 (각 feature만으로 AUC) → 출처 편향 진단
from sklearn.metrics import roc_auc_score
print("\n[3] 단일 feature AUC (0.5=무의미, 1.0=완벽분리) — 하나가 너무 높으면 출처편향 의심")
from sklearn.impute import SimpleImputer
for f in FEATS:
    v = SimpleImputer(strategy="median").fit_transform(raw[f].reshape(-1, 1)).ravel()
    try:
        auc = roc_auc_score(y, v)
        auc = max(auc, 1 - auc)
        flag = " ⚠️출처편향?" if auc > 0.9 else ""
        print(f"   {f:16} AUC {auc:.3f}{flag}")
    except Exception:
        pass

# 4) 다중공선성 (상관)
print("\n[4] 상관계수 (|r|>0.8 = 다중공선성)")
X = np.column_stack([SimpleImputer(strategy="median").fit_transform(raw[f].reshape(-1, 1)).ravel() for f in FEATS])
corr = np.corrcoef(X.T)
for i in range(len(FEATS)):
    for j in range(i + 1, len(FEATS)):
        if abs(corr[i, j]) > 0.8:
            print(f"   {FEATS[i]} ~ {FEATS[j]}: r={corr[i, j]:.2f}")

# 5) 스케일 문제 진단 (왜도)
from scipy.stats import skew
print("\n[5] 왜도(skewness) — |skew|>2 면 로그변환 필요")
for f in FEATS:
    v = raw[f][~np.isnan(raw[f])]
    s = skew(v)
    flag = " → log변환 권장" if abs(s) > 2 else ""
    print(f"   {f:16} skew {s:8.2f}{flag}")

# 6) 라벨 검증: 러그 샘플이 실제 rugged인지 (RugCheck rugged 플래그)
print("\n[6] 라벨 정확성 — 러그 샘플의 실제 상태")
rug_rows = [r for r, l in data if l == 1]
rugged = sum(1 for r in rug_rows if r.get("rugged") == "1")
print(f"   러그 라벨 {len(rug_rows)}개 중 RugCheck rugged=1: {rugged} ({100*rugged/len(rug_rows):.1f}%)")
print(f"   → rugged=0 대다수면 '러그 확정' 아니라 '스캠 의심' 라벨 (라벨 약함)")
