# -*- coding: utf-8 -*-
"""E7 — 생성자 이력이 러그를 예측하는가 (조기탐지, t=0 가능한 신호).
creator_rug_rate = 생성자의 다른 토큰들 중 죽은(러그) 비율. 현 토큰 제외 → 누수 없음.
측정: 단독 판별력, 홀더집중(E2)과 비교/결합, 커버리지, 고위험 생성자의 실제 결과.
입력: creator_history.csv (+ features_helius.csv). 사용: python e7_creator.py
"""
import csv, os, warnings
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
CH = {r["mint"]: r for r in csv.DictReader(open(os.path.join(D, "data", "creator_history.csv"), encoding="utf-8"))}
H = {r["mint"]: r for r in csv.DictReader(open(os.path.join(D, "data", "features_helius.csv"), encoding="utf-8")) if r["status"] == "ok"}

allrows = list(CH.values())
y_all = np.array([int(r["label"]) for r in allrows])
print(f"=== E7 생성자 이력 (수집 {len(allrows)}, 러그 {int(y_all.sum())}/정상 {int((y_all==0).sum())}) ===")

# 커버리지
def fnum(r, k):
    try:
        return float(r[k])
    except (ValueError, TypeError):
        return np.nan
with_hist = [r for r in allrows if r.get("n_other") not in ("", None) and int(float(r["n_other"])) >= 1]
solo = [r for r in allrows if r.get("n_other") not in ("", None) and int(float(r["n_other"])) == 0]
nocr = [r for r in allrows if not r.get("creator")]
print(f"커버리지: 이력있음(다른토큰≥1) {len(with_hist)} / 단독(1개만) {len(solo)} / 생성자실패 {len(nocr)}")
print(f"  → 이력 활용가능 비율 {100*len(with_hist)/len(allrows):.1f}%\n")

# creator_rug_rate 분포 (라벨별)
print("=== creator_rug_rate 분포 (이력있는 토큰) ===")
for lab, nm in [(1, "러그(Inactive)"), (0, "정상(Active)")]:
    v = np.array([fnum(r, "creator_rug_rate") for r in with_hist if int(r["label"]) == lab])
    v = v[~np.isnan(v)]
    if len(v):
        print(f"  {nm:16} n={len(v):4}  평균 {v.mean():.3f}  중앙 {np.median(v):.3f}  (≥0.8 비율 {100*np.mean(v>=0.8):.0f}%)")

# 단독 판별 AUC
from sklearn.metrics import roc_auc_score
yh = np.array([int(r["label"]) for r in with_hist])
def auc1(vals, nm):
    v = np.array(vals); m = ~np.isnan(v)
    if len(set(yh[m])) < 2:
        print(f"  {nm}: 단일클래스"); return
    a = roc_auc_score(yh[m], v[m]); a = max(a, 1 - a)
    print(f"  {nm:26} AUC {a:.3f}  {'★강함' if a>0.7 else '갈림' if a>0.6 else '약함'}")
print("\n=== 생성자 feature 단독 판별력 (이력있는 토큰) ===")
auc1([fnum(r, "creator_rug_rate") for r in with_hist], "creator_rug_rate")
auc1([fnum(r, "n_creator_tokens") for r in with_hist], "n_creator_tokens(포트폴리오크기)")

# 고위험 생성자 → 실제 결과
print("\n=== 생성자 러그율 구간별 실제 러그(라벨=1) 비율 ===")
rr = np.array([fnum(r, "creator_rug_rate") for r in with_hist])
for lo, hi in [(0, 0.2), (0.2, 0.8), (0.8, 1.01)]:
    idx = [i for i in range(len(with_hist)) if not np.isnan(rr[i]) and lo <= rr[i] < hi]
    if idx:
        actual = np.mean([int(with_hist[i]["label"]) for i in idx])
        print(f"  생성자러그율 {lo:.1f}~{hi:.1f}: 토큰 {len(idx):4}개, 실제 러그비율 {100*actual:.0f}%")

# 홀더집중(E2)과 비교/결합
from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.impute import SimpleImputer
import xgboost as xgb
cv = StratifiedKFold(5, shuffle=True, random_state=42)
HFEAT = ["top1_pct", "top5_pct", "top10_pct", "top20_pct", "hhi", "n_holders"]
joint = [r for r in with_hist if r["mint"] in H]
if len(joint) > 30:
    yj = np.array([int(r["label"]) for r in joint])
    cr = np.array([[fnum(r, "creator_rug_rate"), fnum(r, "n_creator_tokens")] for r in joint])
    hd = np.array([[float(H[r["mint"]][f]) if H[r["mint"]].get(f) not in (None, "") else np.nan for f in HFEAT] for r in joint])
    def run(X, tag):
        X = SimpleImputer(strategy="median").fit_transform(X)
        m = xgb.XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.08,
                              scale_pos_weight=float((yj==0).sum())/max(1,(yj==1).sum()),
                              eval_metric="logloss", random_state=42)
        r = cross_validate(m, X, yj, cv=cv, scoring=["roc_auc"])
        print(f"  {tag:30} AUC {r['test_roc_auc'].mean():.3f}")
    print(f"\n=== 결합 (홀더집중 vs 생성자이력 vs 결합, n={len(joint)}) ===")
    run(hd, "홀더집중만(E2)")
    run(cr, "생성자이력만")
    run(np.column_stack([hd, cr]), "결합")
