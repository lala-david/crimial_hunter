# -*- coding: utf-8 -*-
"""라벨 정제 = 결과변수 '분포'를 보고 데이터로 경계를 정하는 것 (스케일링은 feature용, 별개).
여러 죽음/생존 신호를 정규화(min-max)해 하나의 '러그 심각도 점수'로 합치고,
그 점수의 분포에서 자연스러운 경계(이봉 사이 골짜기)로 깨끗한 라벨을 만든다.
입력: features_helius.csv(홀더+라벨) + SolRPDS(유동성/타임스탬프). 사용: python label_refine.py
"""
import csv, glob, os, warnings, datetime
import numpy as np
warnings.filterwarnings("ignore")

D = os.path.dirname(os.path.abspath(__file__))

def ts(s):
    try:
        return datetime.datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S.%f").timestamp()
    except Exception:
        return None

def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return np.nan

# 우리 표본(홀더+라벨)
H = {r["mint"]: r for r in csv.DictReader(open(os.path.join(D, "data", "features_helius.csv"), encoding="utf-8"))
     if r["status"] == "ok"}
# SolRPDS 결과변수 (mint당 첫 풀)
SR = {}
for f in sorted(glob.glob(os.path.join(D, "..", "raw", "solrpds", "*.csv"))):
    for r in csv.DictReader(open(f, encoding="utf-8")):
        m = r.get("MINT")
        if m in H and m not in SR:
            add, rem = fnum(r["TOTAL_ADDED_LIQUIDITY"]), fnum(r["TOTAL_REMOVED_LIQUIDITY"])
            t0 = ts(r["FIRST_POOL_ACTIVITY_TIMESTAMP"]); tl = ts(r["LAST_SWAP_TIMESTAMP"]) or ts(r["LAST_POOL_ACTIVITY_TIMESTAMP"])
            SR[m] = dict(removal_ratio=(rem / add) if add and add > 0 else np.nan,   # 제거/추가 (높을수록 드레인)
                         num_removes=fnum(r["NUM_LIQUIDITY_REMOVES"]),
                         life_h=((tl - t0) / 3600) if (t0 and tl) else np.nan,        # 진짜 활동수명(dust 아님)
                         label=int(H[m]["label"]))
mints = [m for m in H if m in SR]
y = np.array([SR[m]["label"] for m in mints])
print(f"표본 {len(mints)} (러그 {int(y.sum())}/정상 {int((y==0).sum())})\n")

# ── [1] 결과변수 분포 (러그 vs 정상) — 라벨 정제의 원천 ──
print("=== [1] 결과변수 분포 (러그 / 정상, 백분위) — 어디서 갈리나 ===")
for key, nm in [("removal_ratio", "제거/추가비율"), ("life_h", "활동수명(h)"), ("num_removes", "제거횟수")]:
    rv = np.array([SR[m][key] for m in mints if SR[m]["label"] == 1], float); rv = rv[~np.isnan(rv)]
    lv = np.array([SR[m][key] for m in mints if SR[m]["label"] == 0], float); lv = lv[~np.isnan(lv)]
    print(f"  {nm:12} 러그 p25/50/75 = {np.percentile(rv,25):8.2f}/{np.percentile(rv,50):8.2f}/{np.percentile(rv,75):8.2f}"
          f"   정상 = {np.percentile(lv,25):8.2f}/{np.percentile(lv,50):8.2f}/{np.percentile(lv,75):8.2f}")

# ── [2] 신호 정규화(min-max) 후 합성 '러그 심각도 점수' ──
# 여러 신호를 [0,1]로 정규화해 더해야 스케일이 달라도 공정하게 합쳐진다 = 여기서 정규화가 쓰임
def minmax(vals):
    v = np.array(vals, float)
    lo, hi = np.nanpercentile(v, 5), np.nanpercentile(v, 95)   # 이상치에 강하게 5~95%로 클립
    return np.clip((v - lo) / (hi - lo + 1e-9), 0, 1)

rr = minmax([SR[m]["removal_ratio"] for m in mints])           # 드레인 클수록 러그 ↑
life = minmax([SR[m]["life_h"] for m in mints])                # 수명 짧을수록 러그 ↑ → 역방향
sev = np.nanmean(np.column_stack([rr, 1 - life]), axis=1)      # 합성 심각도 [0,1]
sev = np.where(np.isnan(sev), np.nanmedian(sev), sev)
print("\n=== [2] 합성 러그심각도 점수 분포 (min-max 정규화 후 결합) ===")
for lab, nm in [(1, "러그"), (0, "정상")]:
    s = sev[y == lab]
    print(f"  {nm}: p10/25/50/75/90 = " + "/".join(f"{np.percentile(s,p):.2f}" for p in [10,25,50,75,90]))
# 히스토그램(텍스트) — 이봉/골짜기 확인
print("  분포(10구간):")
h, edges = np.histogram(sev, bins=10, range=(0, 1))
for i in range(10):
    print(f"    {edges[i]:.1f}-{edges[i+1]:.1f} | {'█'*int(40*h[i]/max(h))} {h[i]}")

# ── [3] 데이터로 경계 정하기: 애매한 중간(0.4~0.6) 제거 → 깨끗한 라벨 ──
lo, hi = 0.45, 0.55
clean = [i for i in range(len(mints)) if sev[i] <= lo or sev[i] >= hi]
# 정제 라벨: 심각도 기준(원 라벨과 대조도 함께)
print(f"\n=== [3] 데이터 기반 정제: 애매경계({lo}~{hi}) 제거 → {len(clean)}/{len(mints)} 유지 ===")

from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.impute import SimpleImputer
import xgboost as xgb
HFEAT = ["top1_pct", "top5_pct", "top10_pct", "top20_pct", "hhi", "n_holders"]
cv = StratifiedKFold(5, shuffle=True, random_state=42)

def auc_on(idx, tag, labels=None):
    ms = [mints[i] for i in idx]
    yy = np.array(labels) if labels is not None else np.array([SR[m]["label"] for m in ms])
    if len(set(yy)) < 2:
        print(f"  {tag}: 한 클래스뿐 — skip"); return
    X = np.column_stack([[float(H[m][f]) if H[m].get(f) not in (None,"") else np.nan for m in ms] for f in HFEAT])
    X = SimpleImputer(strategy="median").fit_transform(X)
    spw = float((yy==0).sum())/max(1,(yy==1).sum())
    m = xgb.XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.08, scale_pos_weight=spw,
                          eval_metric="logloss", random_state=42)
    a = cross_validate(m, X, yy, cv=cv, scoring=["roc_auc"])["test_roc_auc"].mean()
    print(f"  {tag:38} n={len(ms):4} (러그{int(yy.sum())}/정상{int((yy==0).sum())})  AUC {a:.3f}")

auc_on(list(range(len(mints))), "(A) 원 라벨 전체(노이즈)")
# 정제 A: 원 라벨 유지하되 애매경계 토큰만 제거
auc_on(clean, "(B) 애매경계 제거(원 라벨 유지)")
# 정제 B: 심각도 점수로 라벨 재정의(≥hi=러그1 / ≤lo=정상0)
relabel = [(i, 1 if sev[i] >= hi else 0) for i in clean]
auc_on([i for i,_ in relabel], "(C) 심각도로 라벨 재정의", labels=[l for _,l in relabel])
print("\n→ 라벨 정제 = 결과변수 분포에서 애매한 중간을 제거/재정의. 정규화는 여러 신호를 공정 결합할 때 사용.")
