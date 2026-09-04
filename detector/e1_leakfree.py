# -*- coding: utf-8 -*-
"""E1 — 누수 없는 베이스라인 러그 탐지기 (Helius 불필요, 지금 실행 가능).
목적: 파이프라인 확립 — (1) 동일집단 온체인 라벨(SolRPDS) (2) 엄격한 누수 배제
     (3) 시간분할(과거→미래) (4) 고정밀 블록리스트 운영점(정밀도≥95%→재현율)
     (5) 확률보정 (6) 모델 저장. E2에서 Helius feature를 이 파이프라인에 얹는다.

누수 배제(중요): rem/nr/ratio/rem_to_add/life 는 러그가 '일어난 뒤'에만 확정 →
사후 정보라 제외. add측(미끼 유동성)만 조기 관측 가능 → E1은 add측만.
E1은 의도적으로 얇다(성능의 하한). 강한 신호(홀더집중·첫구간 tx)는 E2(Helius)에서.
"""
import csv, glob, os, json, warnings, datetime, pickle
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
FILES = sorted(glob.glob(os.path.join(D, "..", "raw", "solrpds", "*.csv")))

def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return np.nan

def load():
    rows = []
    for f in FILES:
        yr = int(os.path.basename(f)[:4])
        for r in csv.DictReader(open(f, encoding="utf-8")):
            st = r.get("INACTIVITY_STATUS")
            if st not in ("Active", "Inactive"):
                continue
            add = fnum(r["TOTAL_ADDED_LIQUIDITY"])
            na = fnum(r["NUM_LIQUIDITY_ADDS"])
            rows.append(dict(year=yr, y=1 if st == "Inactive" else 0, add=add, na=na))
    return rows

rows = load()
# 엄격 누수배제: add측만. per_add = 회당 평균 추가규모 (add/na) — 역시 add측이라 누수 없음
LEAKFREE = ["add", "na", "add_per_event"]
for r in rows:
    r["add_per_event"] = (r["add"] / r["na"]) if (r["na"] and r["na"] > 0) else np.nan

def build(subset):
    X = np.column_stack([np.log1p(np.clip(np.array([rows[i][f] for i in subset], float), 0, None))
                         for f in LEAKFREE])
    from sklearn.impute import SimpleImputer
    X = SimpleImputer(strategy="median").fit_transform(X)
    y = np.array([rows[i]["y"] for i in subset])
    return X, y

# 시간분할: 2021-2023 학습 → 2024 테스트 (실제 배포 상황 = 과거로 배워 미래를 막는다)
tr = [i for i, r in enumerate(rows) if r["year"] <= 2023]
te = [i for i, r in enumerate(rows) if r["year"] == 2024]
Xtr, ytr = build(tr); Xte, yte = build(te)
print(f"=== E1 누수없는 베이스라인 (feature={LEAKFREE}) ===")
print(f"학습 2021-2023: {len(ytr)} (러그 {int(ytr.sum())}) → 테스트 2024: {len(yte)} (러그 {int(yte.sum())})\n")

from sklearn.metrics import (roc_auc_score, average_precision_score, precision_recall_curve,
                             f1_score, matthews_corrcoef, precision_score, recall_score)
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb

spw = float((ytr == 0).sum()) / max(1, (ytr == 1).sum())
base = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.08,
                         scale_pos_weight=spw, eval_metric="logloss", random_state=42)
# 확률보정 (블록리스트는 신뢰 가능한 확률이 중요) — isotonic, 학습셋 내부 CV
clf = CalibratedClassifierCV(base, method="isotonic", cv=3)
clf.fit(Xtr, ytr)
proba = clf.predict_proba(Xte)[:, 1]

auc = roc_auc_score(yte, proba); ap = average_precision_score(yte, proba)
print(f"랭킹 지표:  AUC {auc:.3f}   PR-AUC {ap:.3f}   (기저 러그율 {yte.mean():.3f})")

# ── 고정밀 블록리스트 운영점: 정밀도 목표별로 도달 가능한 재현율 ──
prec, rec, thr = precision_recall_curve(yte, proba)
print(f"\n=== 고정밀 블록리스트 운영점 (정밀도 목표 → 재현율/임계값) ===")
print(f"{'목표 정밀도':>10} {'실제 정밀도':>10} {'재현율':>8} {'임계값':>8} {'차단수':>8}")
picks = {}
for target in [0.99, 0.97, 0.95, 0.90]:
    ok = np.where(prec[:-1] >= target)[0]
    if len(ok) == 0:
        print(f"{target:>10.2f}   (도달 불가)")
        continue
    j = ok[np.argmax(rec[:-1][ok])]     # 그 정밀도 이상에서 재현율 최대인 지점
    t = thr[j]; pred = (proba >= t).astype(int)
    print(f"{target:>10.2f} {prec[j]:>10.3f} {rec[j]:>8.3f} {t:>8.3f} {int(pred.sum()):>8}")
    picks[target] = dict(threshold=float(t), precision=float(prec[j]), recall=float(rec[j]))

# 기본 임계 0.5 참고 성능
pred05 = (proba >= 0.5).astype(int)
print(f"\n참고(임계 0.5): F1 {f1_score(yte,pred05):.3f}  MCC {matthews_corrcoef(yte,pred05):.3f} "
      f"정밀도 {precision_score(yte,pred05,zero_division=0):.3f} 재현율 {recall_score(yte,pred05):.3f}")

# feature 중요도
base.fit(Xtr, ytr)
print("\nfeature 중요도(gain):", {LEAKFREE[i]: round(float(v), 3) for i, v in enumerate(base.feature_importances_)})
print("러그 vs 정상 median:", {f: (round(float(np.nanmedian([rows[i][f] for i in te if rows[i]['y']==1])),1),
                                   round(float(np.nanmedian([rows[i][f] for i in te if rows[i]['y']==0])),1)) for f in LEAKFREE})

# 모델 + 메타 저장
os.makedirs(os.path.join(D, "models"), exist_ok=True)
with open(os.path.join(D, "models", "e1_leakfree.pkl"), "wb") as fp:
    pickle.dump({"model": clf, "features": LEAKFREE, "log1p": True}, fp)
meta = dict(experiment="E1_leakfree", features=LEAKFREE, auc=float(auc), pr_auc=float(ap),
            base_rate=float(yte.mean()), operating_points=picks,
            note="누수배제 add측만. E2에서 Helius 홀더집중·첫구간tx 추가 예정")
json.dump(meta, open(os.path.join(D, "models", "e1_metrics.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n저장: detector/models/e1_leakfree.pkl + e1_metrics.json")
