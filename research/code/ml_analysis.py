# -*- coding: utf-8 -*-
"""러그 vs 정상 온체인 특징 — 모델 비교 + feature importance + PCA/tSNE.
데이터: token_features(러그) + control_features(정상). 논문 주장(트리>딥러닝)을 우리 데이터로 검증.
"""
import csv, os, warnings
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
# 벤더 판정값(score/insiders/creator) 전부 제외 — leakage 소지. 순수 온체인 실측만.
FEATS = ["mint_auth_live", "freeze_auth_live", "top1_pct", "top10_pct",
         "total_holders", "lp_providers", "liquidity_usd"]

def load(name, label):
    rows = [r for r in csv.DictReader(open(os.path.join(D, "..", "data", name), encoding="utf-8")) if r["status"] == "ok"]
    X, y = [], []
    for r in rows:
        vec = []
        ok = True
        for f in FEATS:
            v = r.get(f, "")
            try:
                vec.append(float(v))
            except (TypeError, ValueError):
                vec.append(np.nan)
        X.append(vec)
        y.append(label)
    return X, y

Xr, yr = load("token_features.csv", 1)      # 러그
Xc, yc = load("control_features.csv", 0)    # 정상
X = np.array(Xr + Xc, dtype=float)
y = np.array(yr + yc)
# 결측 → 중앙값 대체
from sklearn.impute import SimpleImputer
X = SimpleImputer(strategy="median").fit_transform(X)
print(f"데이터: 러그 {sum(y==1)} / 정상 {sum(y==0)} / feature {X.shape[1]}개\n")

from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
import xgboost as xgb

cv = StratifiedKFold(5, shuffle=True, random_state=42)
scoring = ["f1", "matthews_corrcoef", "average_precision", "roc_auc"]
models = {
    "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
    "RandomForest": RandomForestClassifier(n_estimators=400, max_depth=16, class_weight="balanced", random_state=42),
    "GradientBoosting": GradientBoostingClassifier(n_estimators=300, random_state=42),
    "XGBoost": xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
                                 scale_pos_weight=sum(y == 0) / sum(y == 1), eval_metric="logloss", random_state=42),
    "MLP (뉴럴넷)": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(256, 128),
                                 max_iter=500, early_stopping=True, random_state=42)),
}
print("=== 모델 비교 (5-fold CV) ===")
print(f"{'모델':22} {'F1':>7} {'MCC':>7} {'AUCPRC':>8} {'AUC':>7}")
results = {}
for name, m in models.items():
    r = cross_validate(m, X, y, cv=cv, scoring=scoring)
    f1, mcc = r["test_f1"].mean(), r["test_matthews_corrcoef"].mean()
    ap, auc = r["test_average_precision"].mean(), r["test_roc_auc"].mean()
    results[name] = (f1, mcc, ap, auc)
    print(f"{name:22} {f1:7.3f} {mcc:7.3f} {ap:8.3f} {auc:7.3f}")

# 최고 트리 vs 뉴럴넷
tree_mcc = max(results["RandomForest"][1], results["XGBoost"][1], results["GradientBoosting"][1])
nn_mcc = results["MLP (뉴럴넷)"][1]
print(f"\n[팩트체크] 최고 트리 MCC {tree_mcc:.3f} vs 뉴럴넷(MLP) MCC {nn_mcc:.3f} "
      f"→ {'트리 우세 (논문과 일치)' if tree_mcc > nn_mcc else '뉴럴넷 우세'}")

# Feature importance (XGBoost gain + permutation)
from sklearn.model_selection import train_test_split
from sklearn.inspection import permutation_importance
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
xgbm = xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
                         scale_pos_weight=sum(ytr == 0) / sum(ytr == 1), eval_metric="logloss", random_state=42)
xgbm.fit(Xtr, ytr)
gain = xgbm.feature_importances_
perm = permutation_importance(xgbm, Xte, yte, n_repeats=10, random_state=42, scoring="f1")
print("\n=== Feature Importance (판별력 순) ===")
print(f"{'feature':20} {'XGB gain':>10} {'permutation':>12}")
order = np.argsort(perm.importances_mean)[::-1]
for i in order:
    print(f"{FEATS[i]:20} {gain[i]:10.3f} {perm.importances_mean[i]:12.4f}")

# PCA + tSNE 시각화
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
Xs = StandardScaler().fit_transform(X)
fig, ax = plt.subplots(1, 2, figsize=(14, 6))
pca = PCA(2).fit_transform(Xs)
for lab, c, nm in [(1, "#d64545", "rug"), (0, "#3b82c4", "legit")]:
    ax[0].scatter(pca[y == lab, 0], pca[y == lab, 1], s=8, alpha=0.5, c=c, label=nm)
ax[0].set_title("PCA (2D): rug vs legit"); ax[0].legend()
ts = TSNE(2, perplexity=30, random_state=42, init="pca").fit_transform(Xs)
for lab, c, nm in [(1, "#d64545", "rug"), (0, "#3b82c4", "legit")]:
    ax[1].scatter(ts[y == lab, 0], ts[y == lab, 1], s=8, alpha=0.5, c=c, label=nm)
ax[1].set_title("t-SNE (2D)"); ax[1].legend()
plt.tight_layout()
out = os.path.join(D, "..", "figures", "ml_pca_tsne.png")
plt.savefig(out, dpi=110)
print(f"\n시각화 저장: {out}")
