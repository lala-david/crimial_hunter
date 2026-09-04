# -*- coding: utf-8 -*-
"""조기탐지 — 생성자 이력 수집 (t=0 가능한 강신호).
각 토큰: 생성자(mint 생성 tx feePayer) → 그 생성자의 포트폴리오(getAssetsByCreator)
       → 포트폴리오 각 토큰의 러그여부(DexScreener no_pair) → 생성자 러그율(현 토큰 제외).
사용: python collect_creator_history.py [limit]  출력: detector/data/creator_history.csv
"""
import csv, os, sys, json, time, urllib.request, urllib.error
from collections import Counter

D = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.expanduser("~/.helius_key")).read().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else None

def rpc(m, p, tries=4):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode()
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(RPC, data=b, headers={"Content-Type": "application/json"}), timeout=40) as r:
                return json.loads(r.read().decode()).get("result")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2); continue
            return None
        except Exception:
            time.sleep(1)
    return None

def creator_of(mint):
    before, last, pages = None, None, 0
    while pages < 12:
        p = [mint, {"limit": 1000}] if before is None else [mint, {"limit": 1000, "before": before}]
        res = rpc("getSignaturesForAddress", p)
        if not res:
            break
        last = res[-1]; pages += 1
        if len(res) < 1000:
            break
        before = res[-1]["signature"]
    if not last:
        return None
    tx = rpc("getTransaction", [last["signature"], {"maxSupportedTransactionVersion": 0, "encoding": "jsonParsed"}])
    if not tx:
        return None
    keys = tx["transaction"]["message"]["accountKeys"]
    return next((a["pubkey"] for a in keys if a.get("signer") and a.get("writable")), keys[0]["pubkey"] if keys else None)

def portfolio(creator):
    res = rpc("getAssetsByCreator", {"creatorAddress": creator, "onlyVerified": False, "page": 1, "limit": 100})
    if not res:
        return []
    return [it["id"] for it in res.get("items", [])]

def dead_map(mints):
    """DexScreener 배치로 각 mint가 페어 있는지 → 없으면 러그/사망."""
    alive = set()
    for i in range(0, len(mints), 30):
        chunk = mints[i:i + 30]
        try:
            u = "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(chunk)
            prs = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
            for p in (prs or []):
                bt = (p.get("baseToken") or {}).get("address")
                if bt:
                    alive.add(bt)
        except Exception:
            pass
        time.sleep(0.2)
    return {m: (m not in alive) for m in mints}   # True=dead(러그)

labels = {r["mint"]: int(r["label"]) for r in csv.DictReader(open(os.path.join(D, "data", "features_helius.csv"), encoding="utf-8")) if r["status"] == "ok"}
targets = sorted(labels)
if LIMIT:
    step = max(1, len(targets) // LIMIT)
    targets = targets[::step][:LIMIT]

DST = os.path.join(D, "data", "creator_history.csv")
LOCK = DST + ".lock"
if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 1800:
    sys.exit("실행 중")
open(LOCK, "w").write(str(os.getpid()))
done = {r["mint"] for r in csv.DictReader(open(DST, encoding="utf-8"))} if os.path.exists(DST) else set()
todo = [m for m in targets if m not in done]
out = open(DST, "a" if done else "w", newline="", encoding="utf-8")
FIELDS = ["mint", "label", "creator", "n_creator_tokens", "n_other", "creator_rug_rate"]
w = csv.DictWriter(out, fieldnames=FIELDS)
if not done:
    w.writeheader()
print(f"생성자이력 수집 {len(todo)} (완료 {len(done)})", flush=True)

st = Counter()
try:
    for i, mint in enumerate(todo):
        row = {"mint": mint, "label": labels[mint], "creator": "", "n_creator_tokens": "", "n_other": "", "creator_rug_rate": ""}
        c = creator_of(mint)
        if c:
            row["creator"] = c
            port = [m for m in portfolio(c) if m != mint]   # 현 토큰 제외
            row["n_creator_tokens"] = len(port) + 1
            if port:
                dm = dead_map(port)
                dead = sum(1 for m in port if dm[m])
                row["n_other"] = len(port)
                row["creator_rug_rate"] = round(dead / len(port), 4)
                st["with_history"] += 1
            else:
                row["n_other"] = 0
                st["solo"] += 1
        else:
            st["no_creator"] += 1
        w.writerow(row)
        if i % 20 == 0:
            out.flush(); open(LOCK, "w").write(str(os.getpid()))
            print(f"  {i+len(done)}/{len(targets)} {dict(st)}", flush=True)
        time.sleep(0.05)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료 {dict(st)} → {DST}", flush=True)
