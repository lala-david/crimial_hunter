# -*- coding: utf-8 -*-
"""제대로 된 실험 — SolRPDS 원본 (온체인 검증 라벨 + 동일집단 대조군).
해결: (1) 라벨 약함 → INACTIVITY_STATUS = Flipside 36억 tx 기반 온체인 파생 라벨
     (2) 출처편향 → 러그(Inactive)·정상(Active) 모두 같은 추출로 나온 같은 집단
feature(논문): 유동성 add/remove 총량·횟수, add/remove 비율, 수명(last-first).
정직성: 제거횟수는 라벨 정의의 일부 → 순환성 검증(빼고도 측정).
프로토콜: (A) 논문 재현(2022 train→2021 test) (B) robust 5-fold CV.
"""
import csv, glob, os, warnings, datetime
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
FILES = sorted(glob.glob(os.path.join(D, "..", "..", "raw", "solrpds", "*.csv")))

def parse_ts(s):
    try:
        return datetime.datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S.%f").timestamp()
    except Exception:
        return None

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
            add = fnum(r["TOTAL_ADDED_LIQUIDITY"]); rem = fnum(r["TOTAL_REMOVED_LIQUIDITY"])
            na = fnum(r["NUM_LIQUIDITY_ADDS"]); nr = fnum(r["NUM_LIQUIDITY_REMOVES"])
            ratio = fnum(r["ADD_TO_REMOVE_RATIO"])
            t0 = parse_ts(r["FIRST_POOL_ACTIVITY_TIMESTAMP"]); t1 = parse_ts(r["LAST_POOL_ACTIVITY_TIMESTAMP"])
            life = (t1 - t0) / 3600.0 if (t0 and t1) else np.nan   # 수명(시간)
            rem_to_add = rem / add if add and add > 0 else np.nan  # 제거/추가 비율
            rows.append(dict(year=yr, y=1 if st == "Inactive" else 0,
                             add=add, rem=rem, na=na, nr=nr, ratio=ratio,
                             life=life, rem_to_add=rem_to_add))
    return rows

rows = load()
ys = np.array([r["y"] for r in rows])
print(f"=== SolRPDS: 총 {len(rows)} 풀 | Inactive(러그의심) {int(ys.sum())} ({100*ys.mean():.1f}%) / Active {int((ys==0).sum())} ===")
print("라벨=온체인 파생(Flipside 36억 tx) · 러그/정상 동일집단 → 출처편향 없음\n")

# feature 행렬 구성: 왜도 심한 것 log1p (add/rem/na/nr/ratio/life), rem_to_add는 그대로 clip
LOGF = ["add", "rem", "na", "nr", "ratio", "life"]
LINF = ["rem_to_add"]
ALL = LOGF + LINF

def build(feat_list, subset=None):
    idx = range(len(rows)) if subset is None else subset
    cols = []
    for f in feat_list:
        v = np.array([rows[i][f] for i in idx], float)
        if f in LOGF:
            v = np.log1p(np.clip(v, 0, None))
        else:
            v = np.clip(v, 0, 1e6)
        cols.append(v)
    X = np.column_stack(cols)
    from sklearn.impute import SimpleImputer
    X = SimpleImputer(strategy="median").fit_transform(X)
    y = np.array([rows[i]["y"] for i in idx])
    return X, y

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import AdaBoostClassifier, GradientBoostingClassifier, ExtraTreesClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, f1_score, matthews_corrcoef, accuracy_score, precision_score, recall_score
import xgboost as xgb

def evalm(m, Xtr, ytr, Xte, yte):
    m.fit(Xtr, ytr)
    p = m.predict(Xte)
    try:
        pr = m.predict_proba(Xte)[:, 1]
    except Exception:
        pr = m.decision_function(Xte)
    return dict(AUC=roc_auc_score(yte, pr), ACC=accuracy_score(yte, p),
                F1=f1_score(yte, p), Prec=precision_score(yte, p, zero_division=0),
                Rec=recall_score(yte, p), MCC=matthews_corrcoef(yte, p))

# ---------- 프로토콜 A: 논문 재현 (2022 train → 2021 test) ----------
tr = [i for i, r in enumerate(rows) if r["year"] == 2022]
te = [i for i, r in enumerate(rows) if r["year"] == 2021]
Xtr, ytr = build(ALL, tr); Xte, yte = build(ALL, te)
spw = float((ytr == 0).sum()) / max(1, (ytr == 1).sum())
print(f"[A] 논문 재현: train=2022({len(tr)}) → test=2021({len(te)}), feature={ALL}")
print(f"{'모델':20} {'AUC':>6} {'ACC':>6} {'F1':>6} {'Prec':>6} {'Rec':>6} {'MCC':>7}   (논문 MCC)")
paper = {"AdaBoost": .942, "XGBoost": None, "GradientBoosting": None, "ExtraTrees": None,
         "LogReg": .728, "SVM": .626, "MLP(NN)": .735, "kNN": .181}
modelsA = [
    ("AdaBoost", lambda: AdaBoostClassifier(n_estimators=200, random_state=42)),
    ("XGBoost", lambda: xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
                                          scale_pos_weight=spw, eval_metric="logloss", random_state=42)),
    ("GradientBoosting", lambda: GradientBoostingClassifier(n_estimators=200, random_state=42)),
    ("ExtraTrees", lambda: ExtraTreesClassifier(n_estimators=300, class_weight="balanced", random_state=42)),
    ("LogReg", lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced"))),
    ("SVM", lambda: make_pipeline(StandardScaler(), SVC(class_weight="balanced"))),
    ("MLP(NN)", lambda: make_pipeline(StandardScaler(), MLPClassifier((128, 64), max_iter=600, early_stopping=True, random_state=42))),
    ("kNN", lambda: make_pipeline(StandardScaler(), KNeighborsClassifier(5))),
]
for name, mk in modelsA:
    m = evalm(mk(), Xtr, ytr, Xte, yte)
    pp = paper[name]; ps = f"({pp:.3f})" if pp else "(RF대체)"
    print(f"{name:20} {m['AUC']:6.3f} {m['ACC']:6.3f} {m['F1']:6.3f} {m['Prec']:6.3f} {m['Rec']:6.3f} {m['MCC']:7.3f}   {ps}")

# ---------- 프로토콜 B: robust 5-fold CV (전체 데이터) ----------
from sklearn.model_selection import cross_validate, StratifiedKFold
Xf, yf = build(ALL)
spwf = float((yf == 0).sum()) / max(1, (yf == 1).sum())
cv = StratifiedKFold(5, shuffle=True, random_state=42)
sc = ["roc_auc", "f1", "matthews_corrcoef", "average_precision"]
print(f"\n[B] robust 5-fold CV (전체 {len(yf)})")
print(f"{'모델':20} {'AUC':>6} {'F1':>6} {'MCC':>7} {'AUCPRC':>7}")
# 스케일 무관 트리 — 전체
for name, m in [
    ("XGBoost", xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, scale_pos_weight=spwf, eval_metric="logloss", random_state=42)),
    ("AdaBoost", AdaBoostClassifier(n_estimators=200, random_state=42)),
    ("GradientBoosting", GradientBoostingClassifier(n_estimators=200, random_state=42)),
]:
    r = cross_validate(m, Xf, yf, cv=cv, scoring=sc)
    print(f"{name:20} {r['test_roc_auc'].mean():6.3f} {r['test_f1'].mean():6.3f} {r['test_matthews_corrcoef'].mean():7.3f} {r['test_average_precision'].mean():7.3f}")

# 스케일 민감 모델 — 스케일링 비교 (25k 층화 서브샘플, RBF SVM O(n^2) 회피)
rng = np.random.RandomState(42)
pos = np.where(yf == 1)[0]; neg = np.where(yf == 0)[0]
sub = np.concatenate([rng.choice(pos, min(4000, len(pos)), False), rng.choice(neg, min(12000, len(neg)), False)])
Xs, yss = Xf[sub], yf[sub]
print(f"\n[B-2] 스케일링 비교 (스케일 민감 모델, 층화 서브샘플 {len(sub)})")
print(f"{'모델 + 스케일링':28} {'F1':>6} {'MCC':>7} {'AUCPRC':>7}")
for bn, base in [("LogReg", lambda: LogisticRegression(max_iter=2000, class_weight="balanced")),
                 ("SVM(RBF)", lambda: SVC(class_weight="balanced", probability=True)),
                 ("MLP(NN)", lambda: MLPClassifier((128, 64), max_iter=600, early_stopping=True, random_state=42))]:
    for sn, s in [("none", None), ("Standard", StandardScaler()), ("MinMax", MinMaxScaler())]:
        m = make_pipeline(s, base()) if s else base()
        r = cross_validate(m, Xs, yss, cv=cv, scoring=sc)
        print(f"{bn+' + '+sn:28} {r['test_f1'].mean():6.3f} {r['test_matthews_corrcoef'].mean():7.3f} {r['test_average_precision'].mean():7.3f}")
    print()

# ---------- 순환성 검증: 제거횟수(nr) 제거 시 성능 변화 ----------
print("=== 순환성 검증: NUM_LIQUIDITY_REMOVES(라벨 정의 일부) 제거 ===")
xgbm = lambda X, y: cross_validate(xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
        scale_pos_weight=float((y==0).sum())/max(1,(y==1).sum()), eval_metric="logloss", random_state=42),
        X, y, cv=cv, scoring=["matthews_corrcoef", "roc_auc"])
full = xgbm(Xf, yf)
Xno, _ = build([f for f in ALL if f != "nr"])
noc = xgbm(Xno, yf)
print(f"   전체 feature      MCC {full['test_matthews_corrcoef'].mean():.3f}  AUC {full['test_roc_auc'].mean():.3f}")
print(f"   nr 제거           MCC {noc['test_matthews_corrcoef'].mean():.3f}  AUC {noc['test_roc_auc'].mean():.3f}")
d = full['test_matthews_corrcoef'].mean() - noc['test_matthews_corrcoef'].mean()
print(f"   차이 {d:.3f} → {'제거횟수 의존 큼(순환성 주의)' if d > 0.1 else '제거횟수 없이도 견고(순환성 낮음)'}")

# ---------- feature importance ----------
from sklearn.model_selection import train_test_split
from sklearn.inspection import permutation_importance
Xtr2, Xte2, ytr2, yte2 = train_test_split(Xf, yf, test_size=0.3, stratify=yf, random_state=42)
xm = xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
        scale_pos_weight=float((ytr2==0).sum())/max(1,(ytr2==1).sum()), eval_metric="logloss", random_state=42).fit(Xtr2, ytr2)
perm = permutation_importance(xm, Xte2, yte2, n_repeats=8, random_state=42, scoring="f1")
print("\n=== Feature Importance (판별력 순, permutation) ===")
for i in np.argsort(perm.importances_mean)[::-1]:
    print(f"  {ALL[i]:14} gain {xm.feature_importances_[i]:.3f}  perm {perm.importances_mean[i]:.4f}")

# 러그 vs 정상 특징 대비 (원값 median)
print("\n=== Inactive(러그) vs Active(정상) 원값 median ===")
for f in ["add", "rem", "na", "nr", "ratio", "life", "rem_to_add"]:
    v = np.array([r[f] for r in rows], float)
    rm = np.nanmedian(v[ys == 1]); lm = np.nanmedian(v[ys == 0])
    print(f"  {f:12} 러그 {rm:16.3f}  정상 {lm:16.3f}")
