# -*- coding: utf-8 -*-
"""E2 — Helius로 홀더집중·구조 feature 추출 (SolRPDS 동일집단 라벨).
~/.helius_key 필요. 사용: python features_helius.py [샘플수(각 클래스)]  (기본 1500)
출력: detector/data/features_helius.csv  (resume 지원, 락파일)

추출(전부 누수 없음, 탐지시점 관측 가능):
 B 홀더집중: top1/5/10/20%, HHI (풀/LP 소유자 제외), 조회된 홀더수
 A 구조: mint/freeze 권한 생존, Token-2022 여부·위험확장, decimals
라벨: SolRPDS INACTIVITY_STATUS (mint 단위: 어느 풀이라도 Inactive면 러그=1)
죽은 러그도 mint 계정이 살아있으면(pump.fun Token-2022 다수) 홀더 조회 가능.
"""
import csv, glob, os, sys, json, time, urllib.request, urllib.error
from collections import Counter

D = os.path.dirname(os.path.abspath(__file__))
KEYPATH = os.path.expanduser("~/.helius_key")
if not os.path.exists(KEYPATH):
    sys.exit("Helius 키 없음: dashboard.helius.dev 에서 무료 발급 후 `echo KEY > ~/.helius_key`")
HELIUS = open(KEYPATH).read().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS}"
TOKEN2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
POOL_OWNERS = {"5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j", "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
               "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK", "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX",
               "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP", "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"}
RISKY_EXT = {"transferHook", "permanentDelegate", "transferFeeConfig"}
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1500

def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for _ in range(tries):
        try:
            req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode()).get("result")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2); continue
            return None
        except Exception:
            time.sleep(1)
    return None

# ── SolRPDS mint 단위 라벨 ──
def load_labels():
    lab = {}
    for f in sorted(glob.glob(os.path.join(D, "..", "raw", "solrpds", "*.csv"))):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            m, st = r.get("MINT"), r.get("INACTIVITY_STATUS")
            if not m or st not in ("Active", "Inactive"):
                continue
            lab[m] = 1 if (st == "Inactive" or lab.get(m) == 1) else lab.get(m, 0)
    return lab

labels = load_labels()
rugs = [m for m, y in labels.items() if y == 1]
legit = [m for m, y in labels.items() if y == 0]
# 결정적 샘플 (셔플 대신 정렬 후 스텝) — 재현성
rugs.sort(); legit.sort()
def sample(lst, n):
    if len(lst) <= n:
        return lst
    step = len(lst) / n
    return [lst[int(i * step)] for i in range(n)]
targets = [(m, 1) for m in sample(rugs, N)] + [(m, 0) for m in sample(legit, N)]
print(f"라벨: 러그 {len(rugs)} / 정상 {len(legit)} → 샘플 각 {N} = {len(targets)}", flush=True)

FIELDS = ["mint", "label", "status", "top1_pct", "top5_pct", "top10_pct", "top20_pct",
          "hhi", "n_holders", "mint_auth_live", "freeze_auth_live", "is_token2022", "risky_ext", "decimals"]
DST = os.path.join(D, "data", "features_helius.csv")
os.makedirs(os.path.dirname(DST), exist_ok=True)
LOCK = DST + ".lock"
if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 900:
    sys.exit("이미 실행 중")
open(LOCK, "w").write(str(os.getpid()))
done = set()
if os.path.exists(DST):
    done = {r["mint"] for r in csv.DictReader(open(DST, encoding="utf-8"))}
todo = [(m, y) for m, y in targets if m not in done]
out = open(DST, "a" if done else "w", newline="", encoding="utf-8")
w = csv.DictWriter(out, fieldnames=FIELDS)
if not done:
    w.writeheader()
print(f"수집 대상 {len(todo)} (완료 {len(done)})", flush=True)

def owner_of(token_account):
    r = rpc("getAccountInfo", [token_account, {"encoding": "jsonParsed"}])
    try:
        return r["value"]["data"]["parsed"]["info"]["owner"]
    except Exception:
        return None

stat = Counter()
try:
    for k, (mint, label) in enumerate(todo):
        row = {"mint": mint, "label": label, "status": "no_data"}
        # 구조
        info = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        if info and info.get("value"):
            inf = ((info["value"].get("data") or {}).get("parsed") or {}).get("info") or {}
            row["is_token2022"] = int(info["value"].get("owner") == TOKEN2022)
            row["mint_auth_live"] = int(bool(inf.get("mintAuthority")))
            row["freeze_auth_live"] = int(bool(inf.get("freezeAuthority")))
            row["decimals"] = inf.get("decimals")
            exts = [e.get("extension") for e in (inf.get("extensions") or [])]
            row["risky_ext"] = int(any(e in RISKY_EXT for e in exts))
        # 홀더집중
        largest = rpc("getTokenLargestAccounts", [mint])
        supply_res = rpc("getTokenSupply", [mint])
        supply_ui = None
        if supply_res and supply_res.get("value"):
            supply_ui = float(supply_res["value"].get("uiAmount") or 0)
        if largest and largest.get("value") and supply_ui and supply_ui > 0:
            accts = largest["value"]
            # 상위 5개 소유자 확인 → 풀/LP 제외
            filtered = []
            for a in accts:
                amt = float(a.get("uiAmount") or 0)
                if len(filtered) < 5:
                    o = owner_of(a.get("address"))
                    if o in POOL_OWNERS:
                        continue
                filtered.append(amt)
            filtered.sort(reverse=True)
            if filtered:
                tot = supply_ui
                row["top1_pct"] = round(100 * filtered[0] / tot, 3)
                row["top5_pct"] = round(100 * sum(filtered[:5]) / tot, 3)
                row["top10_pct"] = round(100 * sum(filtered[:10]) / tot, 3)
                row["top20_pct"] = round(100 * sum(filtered[:20]) / tot, 3)
                row["hhi"] = round(sum((amt / tot) ** 2 for amt in filtered), 5)
                row["n_holders"] = len(accts)
                row["status"] = "ok"; stat["ok"] += 1
            else:
                stat["only_pool"] += 1
        else:
            stat[row["status"]] += 1
        w.writerow(row)
        if k % 25 == 0:
            out.flush(); open(LOCK, "w").write(str(os.getpid()))
            print(f"  {k+len(done)}/{len(targets)}  {dict(stat)}", flush=True)
        time.sleep(0.11)   # ~9 req/s (Helius 무료 tier 안전)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: {dict(stat)}  → {DST}")
