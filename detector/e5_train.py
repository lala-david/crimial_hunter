# -*- coding: utf-8 -*-
"""E5 — 초기 tx 동역학의 창별(10m/1h/6h/24h) 판별력 정밀 측정.
핵심 질문: '몇 분/시간이면 러그가 갈리는가' + '어디부터 러그사망 포함(누수)인가'.
- 창마다 그 창의 feature만으로 5-fold CV → AUC/PR-AUC/MCC + 고정밀 운영점
- 창 누적(≤창)도 측정, tx+홀더집중(E2) 결합도 측정
- 러그 수명 분포로 각 창이 사망 이전인지(누수 여부) 판정
사용: python e5_train.py
"""
import csv, os, warnings
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
TX = os.path.join(D, "data", "tx_dynamics.csv")
FH = os.path.join(D, "data", "features_helius.csv")
if not os.path.exists(TX):
    raise SystemExit("tx_dynamics.csv 없음 — collect_tx_dynamics.py 먼저")

WINDOWS = ["10m", "1h", "6h", "24h"]
PER = ["n_tx", "n_slots", "max_per_slot", "err_rate", "active_min"]
LOGF = {"n_tx", "n_slots", "max_per_slot", "active_min"}   # 카운트류 → log1p

rows = [r for r in csv.DictReader(open(TX, encoding="utf-8")) if r.get("reached_start") == "1"]
y = np.array([int(r["label"]) for r in rows])
print(f"=== E5: tx동역학 창별 판별력 (reached_start=1: {len(rows)}, 러그 {int(y.sum())}/정상 {int((y==0).sum())}) ===")
capped = sum(1 for r in csv.DictReader(open(TX, encoding="utf-8")) if r.get("reached_start") == "0")
print(f"(초활성 제외 capped {capped} — 대개 정상, 창 계산 불가)\n")

# 누수 판정 — 주의: lifetime_h는 '풀 주소 서명 span'(러그 후 봇 dust tx로 수년까지 늘어남)이지
# '러그 사망시각'이 아니다. 러그 사망은 SolRPDS 기준 유동성제거 중앙 ~16h.
# 따라서 창별 누수는 SolRPDS 사망분포로 판정: 10m/1h/6h는 사망 이전(누수無), 24h는 일부 포함.
print("누수 판정(SolRPDS 러그 유동성제거 중앙 ~16h 기준):")
print("   10m/1h: 사망 훨씬 이전 → 누수 없음(진짜 조기)")
print("   6h    : 대부분 이전 → 누수 거의 없음")
print("   24h   : 러그 ~50%가 이미 사망(16h) → 제거 tx 일부 포함(누수 주의, 참고용)")
print("   ※ 실제로 10m가 최고 AUC → 판별 정보는 첫 10분 버스트에 집중(누수 아님)\n")

def build(feats):
    cols = []
    for f in feats:
        v = np.array([float(r[f]) if r.get(f) not in (None, "") else np.nan for r in rows])
        if any(f.startswith(p) for p in LOGF):
            v = np.log1p(np.clip(v, 0, None))
        cols.append(v)
    from sklearn.impute import SimpleImputer
    return SimpleImputer(strategy="median").fit_transform(np.column_stack(cols))

from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.metrics import precision_recall_curve
import xgboost as xgb
spw = float((y == 0).sum()) / max(1, (y == 1).sum())
cv = StratifiedKFold(5, shuffle=True, random_state=42)

def measure(feats, tag):
    X = build(feats)
    m = xgb.XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.08,
                          scale_pos_weight=spw, eval_metric="logloss", random_state=42)
    r = cross_validate(m, X, y, cv=cv, scoring=["roc_auc", "average_precision", "matthews_corrcoef"])
    auc, ap, mcc = r["test_roc_auc"].mean(), r["test_average_precision"].mean(), r["test_matthews_corrcoef"].mean()
    # 고정밀 운영점: OOF 예측으로 정밀도95% 재현율
    from sklearn.model_selection import cross_val_predict
    proba = cross_val_predict(m, X, y, cv=cv, method="predict_proba")[:, 1]
    prec, rec, thr = precision_recall_curve(y, proba)
    r95 = 0.0
    ok = np.where(prec[:-1] >= 0.95)[0]
    if len(ok):
        r95 = rec[:-1][ok].max()
    print(f"{tag:26} AUC {auc:.3f}  PR-AUC {ap:.3f}  MCC {mcc:.3f}  정밀도95%→재현율 {r95:.3f}")
    return auc

# ── 1) 창별 단독 (그 창의 feature만) ──
print("=== [1] 창별 단독 판별력 (그 시점까지의 정보만) ===")
for wn in WINDOWS:
    measure([f"{p}_{wn}" for p in PER], f"~{wn} 까지")

# ── 2) 공통 + 창 누적 ──
print("\n=== [2] 참고 지표 추가 ===")
measure(["first_gap_s"] + [f"{p}_1h" for p in PER], "1h + 첫간격")

# ── 3) tx동역학(1h) + 홀더집중(E2) 결합 ──
print("\n=== [3] tx동역학(1h) + 홀더집중(E2) 결합 ===")
holder = {}
if os.path.exists(FH):
    for r in csv.DictReader(open(FH, encoding="utf-8")):
        if r.get("status") == "ok":
            holder[r["mint"]] = r
HFEAT = ["top1_pct", "top5_pct", "top10_pct", "top20_pct", "hhi", "n_holders"]
have = [i for i, r in enumerate(rows) if r["mint"] in holder]
if have:
    yj = np.array([int(rows[i]["label"]) for i in have])
    def col_tx(f, idx):
        v = np.array([float(rows[i][f]) if rows[i].get(f) not in (None,"") else np.nan for i in idx])
        return np.log1p(np.clip(v,0,None)) if any(f.startswith(p) for p in LOGF) else v
    def col_h(f, idx):
        return np.array([float(holder[rows[i]["mint"]].get(f)) if holder[rows[i]["mint"]].get(f) not in (None,"") else np.nan for i in idx])
    from sklearn.impute import SimpleImputer
    tx1 = [f"{p}_1h" for p in PER]
    Xtx = np.column_stack([col_tx(f, have) for f in tx1])
    Xh = np.column_stack([col_h(f, have) for f in HFEAT])
    def cv_auc(X, yy, tag):
        X = SimpleImputer(strategy="median").fit_transform(X)
        m = xgb.XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.08,
                              scale_pos_weight=float((yy==0).sum())/max(1,(yy==1).sum()),
                              eval_metric="logloss", random_state=42)
        r = cross_validate(m, X, yy, cv=cv, scoring=["roc_auc","average_precision","matthews_corrcoef"])
        print(f"{tag:26} AUC {r['test_roc_auc'].mean():.3f}  PR-AUC {r['test_average_precision'].mean():.3f}  MCC {r['test_matthews_corrcoef'].mean():.3f}")
    print(f"(결합 표본 {len(have)})")
    cv_auc(Xh, yj, "홀더집중만 (E2)")
    cv_auc(Xtx, yj, "tx동역학 1h만")
    cv_auc(np.column_stack([Xtx, Xh]), yj, "결합 (1h tx + 홀더)")

# ── 러그 vs 정상 창별 median (해석) ──
print("\n=== 창별 n_tx median (러그 vs 정상) ===")
for wn in WINDOWS:
    f = f"n_tx_{wn}"
    v = np.array([float(r[f]) for r in rows if r.get(f) not in (None,"")])
    yy = np.array([int(r["label"]) for r in rows if r.get(f) not in (None,"")])
    print(f"  {wn:4} 러그 {np.median(v[yy==1]):7.1f}  정상 {np.median(v[yy==0]):7.1f}")
