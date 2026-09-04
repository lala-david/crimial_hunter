# -*- coding: utf-8 -*-
"""E2 — Tier-2 ML 탐지기 학습 (Helius 홀더집중·구조 feature).
입력: detector/data/features_helius.csv (features_helius.py 산출)
- XGBoost + isotonic 확률보정, 층화 hold-out + 5-fold CV
- 고정밀 블록리스트 운영점(정밀도 목표별 재현율)
- ablation: 홀더집중만 vs +구조 vs 전체
- 모델 저장 detector/models/e2_tier2.pkl
사용: python e2_train.py
"""
import csv, os, json, warnings, pickle
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(D, "data", "features_helius.csv")
if not os.path.exists(SRC):
    raise SystemExit("features_helius.csv 없음 — 먼저 `python features_helius.py` 실행 (Helius 키 필요)")

HOLDER = ["top1_pct", "top5_pct", "top10_pct", "top20_pct", "hhi", "n_holders"]
STRUCT = ["mint_auth_live", "freeze_auth_live", "is_token2022", "risky_ext"]
ALL = HOLDER + STRUCT

def load():
    rows = [r for r in csv.DictReader(open(SRC, encoding="utf-8")) if r.get("status") == "ok"]
    y = np.array([int(r["label"]) for r in rows])
    def col(f):
        return np.array([float(r[f]) if r.get(f) not in (None, "") else np.nan for r in rows])
    return rows, y, col

rows, y, col = load()
print(f"=== E2 Tier-2 (Helius 홀더집중·구조) ===")
print(f"데이터: 러그 {int(y.sum())} / 정상 {int((y==0).sum())} (status=ok만)\n")

from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split, cross_validate, StratifiedKFold
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (roc_auc_score, average_precision_score, precision_recall_curve,
                             matthews_corrcoef, f1_score)
import xgboost as xgb

def matrix(feats):
    X = np.column_stack([col(f) for f in feats])
    return SimpleImputer(strategy="median").fit_transform(X)

spw = float((y == 0).sum()) / max(1, (y == 1).sum())
cv = StratifiedKFold(5, shuffle=True, random_state=42)

# ── ablation: feature 블록별 5-fold CV ──
print("=== Ablation (5-fold CV) ===")
print(f"{'feature 블록':22} {'AUC':>7} {'PR-AUC':>7} {'MCC':>7}")
for name, feats in [("홀더집중만", HOLDER), ("구조만", STRUCT), ("전체", ALL)]:
    X = matrix(feats)
    m = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.08,
                          scale_pos_weight=spw, eval_metric="logloss", random_state=42)
    r = cross_validate(m, X, y, cv=cv, scoring=["roc_auc", "average_precision", "matthews_corrcoef"])
    print(f"{name:22} {r['test_roc_auc'].mean():7.3f} {r['test_average_precision'].mean():7.3f} "
          f"{r['test_matthews_corrcoef'].mean():7.3f}")

# ── 최종 모델: 전체 feature, hold-out 30% ──
X = matrix(ALL)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
base = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.08,
                         scale_pos_weight=float((ytr==0).sum())/max(1,(ytr==1).sum()),
                         eval_metric="logloss", random_state=42)
clf = CalibratedClassifierCV(base, method="isotonic", cv=3).fit(Xtr, ytr)
proba = clf.predict_proba(Xte)[:, 1]
auc, ap = roc_auc_score(yte, proba), average_precision_score(yte, proba)
print(f"\nhold-out: AUC {auc:.3f}  PR-AUC {ap:.3f}  (기저 러그율 {yte.mean():.3f})")

# ── 고정밀 블록리스트 운영점 ──
prec, rec, thr = precision_recall_curve(yte, proba)
print(f"\n=== 고정밀 블록리스트 운영점 ===")
print(f"{'목표정밀도':>10} {'실제정밀도':>10} {'재현율':>8} {'임계값':>8}")
picks = {}
for t in [0.99, 0.97, 0.95, 0.90]:
    ok = np.where(prec[:-1] >= t)[0]
    if len(ok) == 0:
        print(f"{t:>10.2f}   (도달 불가)"); continue
    j = ok[np.argmax(rec[:-1][ok])]
    print(f"{t:>10.2f} {prec[j]:>10.3f} {rec[j]:>8.3f} {thr[j]:>8.3f}")
    picks[t] = dict(threshold=float(thr[j]), precision=float(prec[j]), recall=float(rec[j]))

# feature 중요도
base.fit(Xtr, ytr)
imp = sorted(zip(ALL, base.feature_importances_), key=lambda x: -x[1])
print("\nfeature 중요도(gain):")
for f, v in imp:
    print(f"  {f:16} {v:.3f}")

os.makedirs(os.path.join(D, "models"), exist_ok=True)
pickle.dump({"model": clf, "features": ALL}, open(os.path.join(D, "models", "e2_tier2.pkl"), "wb"))
json.dump(dict(experiment="E2_tier2", features=ALL, auc=float(auc), pr_auc=float(ap),
               base_rate=float(yte.mean()), operating_points=picks),
          open(os.path.join(D, "models", "e2_metrics.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n저장: detector/models/e2_tier2.pkl + e2_metrics.json")
