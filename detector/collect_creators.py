# -*- coding: utf-8 -*-
"""생성자 이력 조기탐지 1단계 — 각 토큰의 생성자 지갑 추출.
생성자 = mint의 가장 오래된 tx(=생성 tx)의 feePayer(첫 서명자).
사용: python collect_creators.py [limit]   (limit 없으면 전체)
출력: detector/data/creators.csv (mint,label,creator,create_ts)  resume/lock
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

def oldest_sig(mint):
    before, last, pages = None, None, 0
    while pages < 12:
        p = [mint, {"limit": 1000}] if before is None else [mint, {"limit": 1000, "before": before}]
        res = rpc("getSignaturesForAddress", p)
        if not res:
            break
        last = res[-1]; pages += 1
        if len(res) < 1000:
            return last
        before = res[-1]["signature"]
    return last

def creator_of(mint):
    s = oldest_sig(mint)
    if not s:
        return None, None
    tx = rpc("getTransaction", [s["signature"], {"maxSupportedTransactionVersion": 0, "encoding": "jsonParsed"}])
    if not tx:
        return None, s.get("blockTime")
    keys = tx["transaction"]["message"]["accountKeys"]
    payer = next((a["pubkey"] for a in keys if a.get("signer") and a.get("writable")), keys[0]["pubkey"] if keys else None)
    return payer, tx.get("blockTime")

labels = {}
for r in csv.DictReader(open(os.path.join(D, "data", "features_helius.csv"), encoding="utf-8")):
    if r["status"] == "ok":
        labels[r["mint"]] = int(r["label"])
targets = sorted(labels)
if LIMIT:
    # 러그/정상 섞이게 스텝 샘플
    step = max(1, len(targets) // LIMIT)
    targets = targets[::step][:LIMIT]

DST = os.path.join(D, "data", "creators.csv")
LOCK = DST + ".lock"
if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 1200:
    sys.exit("실행 중")
open(LOCK, "w").write(str(os.getpid()))
done = {r["mint"] for r in csv.DictReader(open(DST, encoding="utf-8"))} if os.path.exists(DST) else set()
todo = [m for m in targets if m not in done]
out = open(DST, "a" if done else "w", newline="", encoding="utf-8")
w = csv.DictWriter(out, fieldnames=["mint", "label", "creator", "create_ts"])
if not done:
    w.writeheader()
print(f"생성자 수집 {len(todo)} (완료 {len(done)})", flush=True)

st = Counter()
try:
    for i, mint in enumerate(todo):
        c, ts = creator_of(mint)
        w.writerow({"mint": mint, "label": labels[mint], "creator": c or "", "create_ts": ts or ""})
        st["ok" if c else "fail"] += 1
        if i % 20 == 0:
            out.flush(); open(LOCK, "w").write(str(os.getpid()))
            print(f"  {i+len(done)}/{len(targets)} {dict(st)}", flush=True)
        time.sleep(0.06)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료 {dict(st)} → {DST}", flush=True)
