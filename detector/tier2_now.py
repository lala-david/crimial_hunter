# -*- coding: utf-8 -*-
"""Tier-2 (잠정) — 기존 RugCheck 홀더집중 데이터로 지금 학습 (키 불필요).
목적: detect.py에 ML 두뇌를 오늘 붙인다. 홀더집중 신호는 research/compare에서
     독립 검증됨(top1≥90%=69%@3.4%FPR). 단, 학습데이터는 출처편향(러그=RugCheck/
     정상=Jupiter) → 절대 성능은 낙관적. Helius 오면 SolRPDS 동일집단으로 재학습(e2_train).
입력: research/data/{token_features(러그), control_features(정상)}.csv
출력: detector/models/tier2_rugcheck.pkl (+ metrics)
사용: python tier2_now.py
"""
import csv, os, json, warnings, pickle
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(D, "..", "research", "data")
# 추론시점(Helius getTokenLargestAccounts + DexScreener)에 실제로 얻어지는 feature만.
# total_holders·lp_providers는 추론시 결측→median대체 시 신호왜곡 발생 → 제외(중요도도 0.1대).
FEATS = ["top1_pct", "top10_pct", "liquidity_usd"]
LOG = {"liquidity_usd"}   # 왜도 심함 → log1p

def load(name, label):
    out = []
    for r in csv.DictReader(open(os.path.join(RES, name), encoding="utf-8")):
        if r.get("status") != "ok":
            continue
        out.append((r, label))
    return out

data = load("token_features.csv", 1) + load("control_features.csv", 0)
y = np.array([d[1] for d in data])
cols = []
for f in FEATS:
    v = np.array([float(r.get(f)) if r.get(f) not in (None, "") else np.nan for r, _ in data])
    if f in LOG:
        v = np.log1p(np.clip(v, 0, None))
    cols.append(v)
from sklearn.impute import SimpleImputer
imp = SimpleImputer(strategy="median")
X = imp.fit_transform(np.column_stack(cols))
print(f"=== Tier-2 (잠정, RugCheck 학습) ===")
print(f"데이터: 러그 {int(y.sum())} / 정상 {int((y==0).sum())}  feature={FEATS}")
print("⚠️ 출처편향 학습데이터 → 절대성능 낙관적. Helius+SolRPDS로 재학습 예정\n")

from sklearn.model_selection import train_test_split, cross_validate, StratifiedKFold
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (roc_auc_score, average_precision_score, precision_recall_curve,
                             matthews_corrcoef)
import xgboost as xgb

spw = float((y == 0).sum()) / max(1, (y == 1).sum())
cv = StratifiedKFold(5, shuffle=True, random_state=42)
mk = lambda w=spw: xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08,
                                     scale_pos_weight=w, eval_metric="logloss", random_state=42)
r = cross_validate(mk(), X, y, cv=cv, scoring=["roc_auc", "average_precision", "matthews_corrcoef"])
print(f"5-fold CV: AUC {r['test_roc_auc'].mean():.3f}  PR-AUC {r['test_average_precision'].mean():.3f}  "
      f"MCC {r['test_matthews_corrcoef'].mean():.3f}")

# hold-out + 확률보정 + 고정밀 운영점
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
clf = CalibratedClassifierCV(mk(float((ytr==0).sum())/max(1,(ytr==1).sum())),
                             method="isotonic", cv=3).fit(Xtr, ytr)
proba = clf.predict_proba(Xte)[:, 1]
auc, ap = roc_auc_score(yte, proba), average_precision_score(yte, proba)
prec, rec, thr = precision_recall_curve(yte, proba)
print(f"hold-out: AUC {auc:.3f}  PR-AUC {ap:.3f}  (기저 러그율 {yte.mean():.3f})")
print(f"\n=== 고정밀 블록리스트 운영점 (정밀도 목표→재현율/임계값) ===")
print(f"{'목표정밀도':>10} {'실제정밀도':>10} {'재현율':>8} {'임계값':>8}")
picks = {}
for t in [0.99, 0.97, 0.95, 0.90]:
    ok = np.where(prec[:-1] >= t)[0]
    if len(ok) == 0:
        print(f"{t:>10.2f}   (도달 불가)"); continue
    j = ok[np.argmax(rec[:-1][ok])]
    print(f"{t:>10.2f} {prec[j]:>10.3f} {rec[j]:>8.3f} {thr[j]:>8.3f}")
    picks[str(t)] = dict(threshold=float(thr[j]), precision=float(prec[j]), recall=float(rec[j]))

# feature 중요도
m = mk(); m.fit(Xtr, ytr)
print("\nfeature 중요도(gain):", {FEATS[i]: round(float(v), 3) for i, v in enumerate(m.feature_importances_)})

os.makedirs(os.path.join(D, "models"), exist_ok=True)
pickle.dump({"model": clf, "features": FEATS, "log": list(LOG),
             "medians": imp.statistics_.tolist(), "block_threshold": picks.get("0.95", {}).get("threshold", 0.6)},
            open(os.path.join(D, "models", "tier2_rugcheck.pkl"), "wb"))
json.dump(dict(experiment="tier2_rugcheck_interim", features=FEATS, auc=float(auc), pr_auc=float(ap),
               base_rate=float(yte.mean()), operating_points=picks,
               caveat="출처편향 학습데이터, 절대성능 낙관적. Helius+SolRPDS 재학습으로 대체 예정"),
          open(os.path.join(D, "models", "tier2_metrics.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n저장: detector/models/tier2_rugcheck.pkl + tier2_metrics.json")
