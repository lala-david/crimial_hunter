# -*- coding: utf-8 -*-
"""솔라나 토큰 전체 온체인 스캔 → 정확한 카테고리 분류.
getMultipleAccounts(jsonParsed) 100개 배치로 전량 조회.
수집: 계정존재, owner 프로그램(SPL/Token-2022/AMM/System), 계정타입(mint/account),
      mint 권한(mintAuthority/freezeAuthority), supply, decimals, Token-2022 확장.
사용법: python scan_all_sol.py [출력.csv]
- 이어받기(락파일), 레이트리밋 백오프
"""
import csv, json, os, sys, time, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(BASE, "solana", "master_solana_tokens.csv")
DST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sol_onchain_scan.csv")
LOCK = DST + ".lock"
RPC = "https://api.mainnet-beta.solana.com"

# 주요 프로그램 ID
PROG = {
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "SPL_TOKEN",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "TOKEN_2022",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "RAYDIUM_AMM",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "RAYDIUM_CPMM",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "ORCA_WHIRLPOOL",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "PUMP_FUN",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "METEORA_DLMM",
    "11111111111111111111111111111111": "SYSTEM",
}

if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 900:
    sys.exit("다른 인스턴스 실행 중")
open(LOCK, "w").write(str(os.getpid()))

def rpc(batch):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
                       "params": [batch, {"encoding": "jsonParsed"}]}).encode()
    delay = 2
    for _ in range(9):
        try:
            req = urllib.request.Request(RPC, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode())
            if "result" in d:
                return d["result"]["value"]
            time.sleep(delay); delay = min(30, delay * 1.7)
        except Exception:
            time.sleep(delay); delay = min(30, delay * 1.7)
    return None

FIELDS = ["address", "exists", "owner_prog", "acct_type",
          "mint_auth", "freeze_auth", "supply", "decimals", "token2022_ext"]

done = set()
if os.path.exists(DST):
    for r in csv.DictReader(open(DST, encoding="utf-8")):
        done.add(r["address"])
targets = []
for r in csv.DictReader(open(SRC, encoding="utf-8")):
    a = (r.get("address") or "").strip()
    if a and a not in done:
        targets.append(a)
print(f"스캔 대상 {len(targets)} (완료 {len(done)})", flush=True)

out = open(DST, "a" if done else "w", newline="", encoding="utf-8")
w = csv.DictWriter(out, fieldnames=FIELDS)
if not done:
    w.writeheader()

from collections import Counter
stat = Counter()
try:
    for i in range(0, len(targets), 100):
        batch = targets[i:i + 100]
        vals = rpc(batch)
        if vals is None:
            print(f"  배치 {i} 실패 — 스킵", flush=True)
            continue
        for addr, v in zip(batch, vals):
            if v is None:
                w.writerow({"address": addr, "exists": 0, "owner_prog": "", "acct_type": "CLOSED"})
                stat["CLOSED"] += 1
                continue
            owner = v.get("owner", "")
            prog = PROG.get(owner, owner[:12])
            parsed = (v.get("data") or {}).get("parsed") if isinstance(v.get("data"), dict) else None
            atype = (parsed or {}).get("type", "")
            info = (parsed or {}).get("info", {}) if parsed else {}
            ext = ""
            if isinstance(info.get("extensions"), list):
                ext = "|".join(e.get("extension", "") for e in info["extensions"])[:60]
            row = {
                "address": addr, "exists": 1, "owner_prog": prog, "acct_type": atype,
                "mint_auth": 1 if info.get("mintAuthority") else 0,
                "freeze_auth": 1 if info.get("freezeAuthority") else 0,
                "supply": info.get("supply", ""),
                "decimals": info.get("decimals", ""),
                "token2022_ext": ext,
            }
            w.writerow(row)
            stat[prog + ":" + (atype or "?")] += 1
        out.flush()
        if (i // 100) % 20 == 0:
            open(LOCK, "w").write(str(os.getpid()))
            print(f"  {i+len(batch)}/{len(targets)}  상위: {dict(Counter(dict(stat)).most_common(4))}", flush=True)
        time.sleep(0.25)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: {dict(stat.most_common())}")
