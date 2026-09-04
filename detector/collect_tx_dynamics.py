# -*- coding: utf-8 -*-
"""E5 — 초기 tx 동역학 수집 (Helius). 다중 시간창별 정밀 측정.
각 풀의 첫 tx(t0) 기준 여러 창(10분/1시간/6시간/24시간)의 활동을 각각 추출 →
'몇 분/시간이면 러그가 갈리는지' + '어디부터 러그사망 포함(누수)인지'를 창별로 안다.
서명(getSignaturesForAddress)의 blockTime/slot/err만 사용(저비용).
러그 중앙 수명 ~16h: 10m/1h는 누수없는 조기, 6h 대체로 조기, 24h는 사망 다수 포함(참고).
대상: features_helius.csv 의 mint. 사용: python collect_tx_dynamics.py
출력: detector/data/tx_dynamics.csv (resume, lock)
"""
import csv, glob, os, sys, json, time, urllib.request, urllib.error
from collections import Counter

D = os.path.dirname(os.path.abspath(__file__))
KEYPATH = os.path.expanduser("~/.helius_key")
if not os.path.exists(KEYPATH):
    sys.exit("Helius 키 없음")
RPC = f"https://mainnet.helius-rpc.com/?api-key={open(KEYPATH).read().strip()}"
PAGE_CAP = 15                                   # 최대 15k tx 파주기. 초과=reached_start=0(초활성≈정상)
WINDOWS = [("10m", 600), ("1h", 3600), ("6h", 21600), ("24h", 86400)]

def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for _ in range(tries):
        try:
            req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode()).get("result")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2); continue
            return None
        except Exception:
            time.sleep(1)
    return None

# 대상 mint(features_helius) + mint→pool (SolRPDS 첫 풀)
targets = {}
fh = os.path.join(D, "data", "features_helius.csv")
if os.path.exists(fh):
    for r in csv.DictReader(open(fh, encoding="utf-8")):
        if r.get("status") == "ok":
            targets[r["mint"]] = int(r["label"])
mint_pool = {}
for f in sorted(glob.glob(os.path.join(D, "..", "raw", "solrpds", "*.csv"))):
    for r in csv.DictReader(open(f, encoding="utf-8")):
        m, p = r.get("MINT"), r.get("LIQUIDITY_POOL_ADDRESS")
        if m in targets and m not in mint_pool and p:
            mint_pool[m] = p
todo_all = [(m, targets[m], mint_pool[m]) for m in targets if m in mint_pool]
print(f"대상 {len(todo_all)} (holder {len(targets)} 중 pool매핑 성공)", flush=True)

# 창별 5개 지표 + 공통
PER = ["n_tx", "n_slots", "max_per_slot", "err_rate", "active_min"]
FIELDS = ["mint", "label", "pool", "reached_start", "total_tx_seen", "lifetime_h", "first_gap_s"]
for wn, _ in WINDOWS:
    FIELDS += [f"{p}_{wn}" for p in PER]

DST = os.path.join(D, "data", "tx_dynamics.csv")
LOCK = DST + ".lock"
if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 1200:
    sys.exit("이미 실행 중")
open(LOCK, "w").write(str(os.getpid()))
done = {r["mint"] for r in csv.DictReader(open(DST, encoding="utf-8"))} if os.path.exists(DST) else set()
todo = [t for t in todo_all if t[0] not in done]
out = open(DST, "a" if done else "w", newline="", encoding="utf-8")
w = csv.DictWriter(out, fieldnames=FIELDS)
if not done:
    w.writeheader()
print(f"수집 {len(todo)} (완료 {len(done)}) | 창={[x[0] for x in WINDOWS]}", flush=True)

def all_sigs(pool):
    sigs, before, pages = [], None, 0
    while pages < PAGE_CAP:
        params = [pool, {"limit": 1000}] if before is None else [pool, {"limit": 1000, "before": before}]
        res = rpc("getSignaturesForAddress", params)
        if not res:
            break
        sigs.extend(res); pages += 1
        if len(res) < 1000:
            return sigs, True
        before = res[-1]["signature"]
    return sigs, False

def win_feats(sigs, t0, W):
    ws = [s for s in sigs if s.get("blockTime") and t0 <= s["blockTime"] <= t0 + W]
    if not ws:
        return {"n_tx": 0, "n_slots": 0, "max_per_slot": 0, "err_rate": 0, "active_min": 0}
    slots = Counter(s["slot"] for s in ws)
    return {"n_tx": len(ws), "n_slots": len(slots), "max_per_slot": max(slots.values()),
            "err_rate": round(sum(1 for s in ws if s.get("err")) / len(ws), 4),
            "active_min": len({s["blockTime"] // 60 for s in ws})}

stat = Counter()
try:
    for k, (mint, label, pool) in enumerate(todo):
        sigs, reached = all_sigs(pool)
        bt = [s["blockTime"] for s in sigs if s.get("blockTime")]
        row = {"mint": mint, "label": label, "pool": pool,
               "reached_start": int(reached), "total_tx_seen": len(sigs)}
        if reached and bt:
            t0, t1 = min(bt), max(bt)
            row["lifetime_h"] = round((t1 - t0) / 3600, 3)
            g = sorted(bt)
            row["first_gap_s"] = (g[1] - g[0]) if len(g) > 1 else 0
            for wn, W in WINDOWS:
                for kk, vv in win_feats(sigs, t0, W).items():
                    row[f"{kk}_{wn}"] = vv
            stat["ok"] += 1
        else:
            stat["capped" if not reached else "no_bt"] += 1
        w.writerow(row)
        if k % 25 == 0:
            out.flush(); open(LOCK, "w").write(str(os.getpid()))
            print(f"  {k+len(done)}/{len(todo_all)}  {dict(stat)}", flush=True)
        time.sleep(0.05)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: {dict(stat)} → {DST}", flush=True)
