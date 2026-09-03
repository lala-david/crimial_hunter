# -*- coding: utf-8 -*-
"""러그 vs 정상 — 순수 온체인 feature 재구현 (leakage 없음).
feature: HHI, 홀더집중(top1/5/10/20), 권한(mint/freeze), Token-2022, decimals.
RugCheck score·insiders·creator_tokens 등 벤더 판정값 전부 배제.
논문(Mazorra HHI, Cernera/From Hype 권한) 기반 실측 feature.
"""
import csv, os, warnings
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))
FEATS = ["top1_pct", "top5_pct", "top10_pct", "top20_pct", "hhi_top20",
         "n_top_holders", "mint_auth_live", "freeze_auth_live", "is_token2022", "decimals"]

rows = [r for r in csv.DictReader(open(os.path.join(D, "..", "data", "holder_features.csv"), encoding="utf-8"))
        if r["status"] == "ok"]
X, y = [], []
for r in rows:
    vec = []
    for f in FEATS:
        try:
            vec.append(float(r.get(f, "")))
        except (TypeError, ValueError):
            vec.append(np.nan)
    X.append(vec)
    y.append(int(r["label"]))
X = np.array(X, dtype=float)
y = np.array(y)
from sklearn.impute import SimpleImputer
X = SimpleImputer(strategy="median").fit_transform(X)
print(f"데이터: 러그 {int((y==1).sum())} / 정상 {int((y==0).sum())} / feature {X.shape[1]}개")
print("feature:", FEATS, "\n")

from sklearn.model_selection import cross_validate, StratifiedKFold, train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.inspection import permutation_importance
import xgboost as xgb

spw = float((y == 0).sum()) / float((y == 1).sum())
cv = StratifiedKFold(5, shuffle=True, random_state=42)
scoring = ["f1", "matthews_corrcoef", "average_precision", "roc_auc"]
models = {
    "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
    "RandomForest": RandomForestClassifier(n_estimators=400, max_depth=16, class_weight="balanced", random_state=42),
    "GradientBoosting": GradientBoostingClassifier(n_estimators=300, random_state=42),
    "XGBoost": xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
                                 scale_pos_weight=spw, eval_metric="logloss", random_state=42),
    "MLP (뉴럴넷)": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(256, 128),
                                 max_iter=500, early_stopping=True, random_state=42)),
}
print("=== 모델 비교 (5-fold CV, 순수 온체인 feature) ===")
print(f"{'모델':22} {'F1':>7} {'MCC':>7} {'AUCPRC':>8} {'AUC':>7}")
res = {}
for name, m in models.items():
    r = cross_validate(m, X, y, cv=cv, scoring=scoring)
    res[name] = (r["test_f1"].mean(), r["test_matthews_corrcoef"].mean(),
                 r["test_average_precision"].mean(), r["test_roc_auc"].mean())
    print(f"{name:22} {res[name][0]:7.3f} {res[name][1]:7.3f} {res[name][2]:8.3f} {res[name][3]:7.3f}")
tree = max(res["RandomForest"][1], res["XGBoost"][1], res["GradientBoosting"][1])
print(f"\n[팩트체크] 최고 트리 MCC {tree:.3f} vs 뉴럴넷 MCC {res['MLP (뉴럴넷)'][1]:.3f} "
      f"→ {'트리 우세' if tree > res['MLP (뉴럴넷)'][1] else '뉴럴넷 우세'}")

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
xgbm = xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
                         scale_pos_weight=float((ytr == 0).sum()) / float((ytr == 1).sum()),
                         eval_metric="logloss", random_state=42).fit(Xtr, ytr)
perm = permutation_importance(xgbm, Xte, yte, n_repeats=10, random_state=42, scoring="f1")
print("\n=== Feature Importance (판별력 순, permutation) ===")
for i in np.argsort(perm.importances_mean)[::-1]:
    print(f"  {FEATS[i]:18} gain {xgbm.feature_importances_[i]:.3f}  perm {perm.importances_mean[i]:.4f}")

# 러그 vs 정상 평균 비교 (팩트)
print("\n=== 러그 vs 정상 온체인 특징 평균 ===")
for i, f in enumerate(FEATS):
    rm, lm = X[y == 1, i].mean(), X[y == 0, i].mean()
    print(f"  {f:18} 러그 {rm:12.3f}  정상 {lm:12.3f}")

# PCA/tSNE
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
Xs = StandardScaler().fit_transform(X)
fig, ax = plt.subplots(1, 2, figsize=(14, 6))
p = PCA(2).fit_transform(Xs)
for lab, c, nm in [(1, "#d64545", "rug"), (0, "#3b82c4", "legit")]:
    ax[0].scatter(p[y == lab, 0], p[y == lab, 1], s=8, alpha=0.5, c=c, label=nm)
ax[0].set_title("PCA (2D): onchain features"); ax[0].legend()
t = TSNE(2, perplexity=30, random_state=42, init="pca").fit_transform(Xs)
for lab, c, nm in [(1, "#d64545", "rug"), (0, "#3b82c4", "legit")]:
    ax[1].scatter(t[y == lab, 0], t[y == lab, 1], s=8, alpha=0.5, c=c, label=nm)
ax[1].set_title("t-SNE (2D): onchain features"); ax[1].legend()
plt.tight_layout()
plt.savefig(os.path.join(D, "..", "figures", "ml_onchain_pca_tsne.png"), dpi=110)
print("\n시각화 저장: research/figures/ml_onchain_pca_tsne.png")
