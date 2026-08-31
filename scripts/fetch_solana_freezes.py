# -*- coding: utf-8 -*-
"""솔라나 USDC/USDT 발행사 동결 지갑 수집 — freeze authority의 freezeAccount 이력 전수 스캔.
Circle·Tether가 솔라나에서 실제 동결한 토큰계정의 owner 지갑 = 발행사 집행 조치(온체인 사실).
- freeze authority는 mint 계정에서 동적 조회
- 서명 이력 → freezeAccount/thawAccount 파싱 (thaw로 해제된 건 상쇄)
- 이어받기: raw/sol_freeze_events.jsonl 에 (sig 단위) append
출력: sources/solana_frozen_stablecoin.csv (owner 지갑)
"""
import csv, json, os, time, urllib.request
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "sources")
EVENTS = os.path.join(RAW, "sol_freeze_events.jsonl")

LOCK = EVENTS + ".lock"
if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 900:
    print("다른 인스턴스 실행 중 — 종료")
    raise SystemExit(0)
open(LOCK, "w").write(str(os.getpid()))
import atexit
atexit.register(lambda: os.path.exists(LOCK) and os.remove(LOCK))

RPC = "https://api.mainnet-beta.solana.com"
MINTS = {"USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
         "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    delay = 2
    for _ in range(8):
        try:
            req = urllib.request.Request(RPC, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode())
            if "result" in d:
                return d["result"]
            time.sleep(delay); delay = min(30, delay * 1.7)
        except Exception:
            time.sleep(delay); delay = min(30, delay * 1.7)
    return None

# ---- 1) freeze authority 조회 ----
authorities = {}
for coin, mint in MINTS.items():
    r = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    fa = (((r or {}).get("value") or {}).get("data", {}).get("parsed", {})
          .get("info", {}).get("freezeAuthority"))
    if fa:
        authorities[coin] = fa
        print(f"{coin} freeze authority: {fa}")
if not authorities:
    raise SystemExit("freeze authority 조회 실패")

done_sigs = set()
if os.path.exists(EVENTS):
    with open(EVENTS, encoding="utf-8") as f:
        for line in f:
            try:
                done_sigs.add(json.loads(line)["sig"])
            except Exception:
                pass
print(f"기존 처리 서명: {len(done_sigs)}")

ev = open(EVENTS, "a", encoding="utf-8")
stats = Counter()
for coin, auth in authorities.items():
    # ---- 2) 서명 이력 수집 (최신→과거) ----
    sigs, before = [], None
    while True:
        params = [auth, {"limit": 1000}]
        if before:
            params[1]["before"] = before
        batch = rpc("getSignaturesForAddress", params)
        if not batch:
            break
        sigs.extend(s["signature"] for s in batch if not s.get("err"))
        before = batch[-1]["signature"]
        print(f"  [{coin}] 서명 {len(sigs)}개 수집...", flush=True)
        if len(batch) < 1000:
            break
        time.sleep(0.3)
    todo = [s for s in sigs if s not in done_sigs]
    print(f"[{coin}] 서명 총 {len(sigs)} / 신규 {len(todo)}")

    # ---- 3) 트랜잭션 파싱: freezeAccount / thawAccount ----
    for i, sig in enumerate(todo):
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed",
                                          "maxSupportedTransactionVersion": 0}])
        recs = []
        if tx:
            msg = (tx.get("transaction") or {}).get("message", {})
            allins = list(msg.get("instructions", []))
            for inner in (tx.get("meta") or {}).get("innerInstructions") or []:
                allins.extend(inner.get("instructions", []))
            bt = tx.get("blockTime") or 0
            for ins in allins:
                p = ins.get("parsed")
                if not isinstance(p, dict):
                    continue
                t = p.get("type")
                if t in ("freezeAccount", "thawAccount"):
                    info = p.get("info", {})
                    recs.append({"sig": sig, "coin": coin, "type": t,
                                 "account": info.get("account"), "time": bt})
                    stats[f"{coin}_{t}"] += 1
        if not recs:
            recs = [{"sig": sig, "coin": coin, "type": "none", "account": None, "time": 0}]
        for rec in recs:
            ev.write(json.dumps(rec) + "\n")
        if (i + 1) % 100 == 0:
            ev.flush()
            print(f"  [{coin}] {i+1}/{len(todo)}  {dict(stats)}", flush=True)
        time.sleep(0.15)
ev.close()

# ---- 4) 계정별 최종 상태 (마지막 이벤트 기준) → owner 지갑 ----
last = {}
with open(EVENTS, encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        if e.get("type") in ("freezeAccount", "thawAccount") and e.get("account"):
            k = (e["coin"], e["account"])
            if k not in last or e["time"] >= last[k][1]:
                last[k] = (e["type"], e["time"])
frozen = [(coin, acct, t) for (coin, acct), (typ, t) in last.items() if typ == "freezeAccount"]
print(f"현재 동결 토큰계정: {len(frozen)}")

# owner 조회 (100개 배치)
owners = {}
accts = [a for _, a, _ in frozen]
for i in range(0, len(accts), 100):
    batch = accts[i:i+100]
    r = rpc("getMultipleAccounts", [batch, {"encoding": "jsonParsed"}])
    for a, v in zip(batch, (r or {}).get("value") or []):
        if v:
            owners[a] = v.get("data", {}).get("parsed", {}).get("info", {}).get("owner", "")
    time.sleep(0.3)

rows = {}
for coin, acct, t in frozen:
    o = owners.get(acct)
    if not o:
        continue
    day = time.strftime("%Y-%m-%d", time.gmtime(t)) if t else ""
    key = o
    if key not in rows:
        rows[key] = [o, "SOL", "enforcement_frozen", f"{coin.lower()}_sol_frozen",
                     f"{coin} frozen onchain", f"token_account={acct[:20]}", day]
with open(os.path.join(OUT, "solana_frozen_stablecoin.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(rows.values())
print(f"-> solana_frozen_stablecoin.csv: owner 지갑 {len(rows)}개  {dict(stats)}")
