# -*- coding: utf-8 -*-
"""제대로 된 실험 — 감사에서 나온 문제 교정.
교정: (1) 로그변환(왜도 심한 feature) (2) 다중공선성 제거(top1 vs top10 중 하나)
     (3) MinMax vs Standard 스케일링 비교 (4) RF 제외, 여러 모델 (5) 출처편향 정직 명시.
라벨 한계(rugged=0, 출처편향)는 데이터 재수집 전까지 해결 불가 — 결과를 그 맥락에서 해석.
"""
import csv, os, warnings
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
# 다중공선성 제거: top1_pct 제외(top10과 r=0.90), 대표로 top10 유지
BIN = ["mint_auth_live", "freeze_auth_live"]        # 이진 — 변환/스케일 불필요
LOG = ["total_holders", "lp_providers", "liquidity_usd"]  # 왜도 심함 → log1p
LIN = ["top10_pct"]                                  # 이미 % (0-100), top1 제외
FEATS = BIN + LOG + LIN

def load(name, label):
    return [(r, label) for r in csv.DictReader(open(os.path.join(D, "..", "data", name), encoding="utf-8")) if r["status"] == "ok"]

data = load("token_features.csv", 1) + load("control_features.csv", 0)
y = np.array([d[1] for d in data])

def col(f):
    out = []
    for r, _ in data:
        try:
            out.append(float(r.get(f, "")))
        except (TypeError, ValueError):
            out.append(np.nan)
    return np.array(out)

from sklearn.impute import SimpleImputer
mats = []
for f in FEATS:
    v = col(f)
    if f in LOG:
        v = np.log1p(np.clip(v, 0, None))   # 로그변환 (음수 방지)
    mats.append(v)
X = np.column_stack(mats)
X = SimpleImputer(strategy="median").fit_transform(X)
print(f"데이터: 러그 {int((y==1).sum())} / 정상 {int((y==0).sum())}")
print(f"feature {FEATS} (LOG={LOG}, top1 제외=다중공선성)\n")

from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier, ExtraTreesClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.pipeline import make_pipeline
import xgboost as xgb

spw = float((y == 0).sum()) / float((y == 1).sum())
cv = StratifiedKFold(5, shuffle=True, random_state=42)
scoring = ["f1", "matthews_corrcoef", "average_precision", "balanced_accuracy"]

# 스케일링 비교: 스케일 민감 모델(LogReg, SVM, MLP)에 None/Standard/MinMax
print("=== 스케일링 비교 (스케일 민감 모델) ===")
print(f"{'모델 + 스케일링':32} {'F1':>7} {'MCC':>7} {'AUCPRC':>8}")
def run(m):
    r = cross_validate(m, X, y, cv=cv, scoring=scoring)
    return r["test_f1"].mean(), r["test_matthews_corrcoef"].mean(), r["test_average_precision"].mean()
for base_name, base in [("LogReg", lambda: LogisticRegression(max_iter=2000, class_weight="balanced")),
                        ("SVM(RBF)", lambda: SVC(class_weight="balanced", probability=True)),
                        ("MLP", lambda: MLPClassifier((128, 64), max_iter=800, early_stopping=True, random_state=42))]:
    for sc_name, sc in [("none", None), ("Standard", StandardScaler()), ("MinMax", MinMaxScaler())]:
        m = make_pipeline(sc, base()) if sc else base()
        f1, mcc, ap = run(m)
        print(f"{base_name+' + '+sc_name:32} {f1:7.3f} {mcc:7.3f} {ap:8.3f}")
    print()

# 트리 모델 (스케일 무관) — RF 제외, 여러 부스팅/트리
print("=== 트리/부스팅 (스케일 무관, RF 제외) ===")
print(f"{'모델':32} {'F1':>7} {'MCC':>7} {'AUCPRC':>8}")
for name, m in [("XGBoost", xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
                                              scale_pos_weight=spw, eval_metric="logloss", random_state=42)),
                ("GradientBoosting", GradientBoostingClassifier(n_estimators=300, random_state=42)),
                ("ExtraTrees", ExtraTreesClassifier(n_estimators=400, class_weight="balanced", random_state=42))]:
    f1, mcc, ap = run(m)
    print(f"{name:32} {f1:7.3f} {mcc:7.3f} {ap:8.3f}")

# 출처편향 정량화: 홀더집중 없이 vs 있이
print("\n=== 출처편향 진단: 홀더집중(top10) 제거 시 성능 변화 ===")
idx_no_conc = [i for i, f in enumerate(FEATS) if f != "top10_pct"]
Xnc = X[:, idx_no_conc]
xgbm = xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05, scale_pos_weight=spw,
                         eval_metric="logloss", random_state=42)
full = cross_validate(xgbm, X, y, cv=cv, scoring=scoring)["test_matthews_corrcoef"].mean()
noconc = cross_validate(xgbm, Xnc, y, cv=cv, scoring=scoring)["test_matthews_corrcoef"].mean()
print(f"   전체 MCC {full:.3f} / 홀더집중 제거 MCC {noconc:.3f}  (차이 {full-noconc:.3f})")
print(f"   → 홀더집중이 대부분을 설명하면 출처편향 의심(정상=대형=분산 / 러그=소형=집중)")
