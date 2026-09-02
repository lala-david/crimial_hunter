# -*- coding: utf-8 -*-
"""풀 주소 전량 검증 (DexScreener 배치) → 러그완료/오탐/활성 판정 + 스캠코인 mint 역추출.
- 무응답 = 유동성 완전 제거(러그 완료)
- base/quote 둘 다 메이저(SOL/USDC/USDT 등) = 오탐(정상 풀)
- 그 외 = 스캠코인 페어, 메이저 아닌 쪽이 스캠 mint
출력: research/pool_verdict.csv
"""
import csv, json, os, sys, time, urllib.request

D = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(D)
SCAN = os.path.join(D, "sol_onchain_scan.csv")
DST = os.path.join(D, "pool_verdict.csv")
LOCK = DST + ".lock"

# 토큰 프로그램/지갑은 풀 아님 → 제외
NON_POOL = {"SPL_TOKEN", "TOKEN_2022", "SYSTEM", "BPFLoaderUpg", "NativeLoader"}
NON_POOL_TYPE = {"mint", "account", "multisig", "program", "programData"}
MAJOR = {  # 메이저/스테이블 — 양쪽 다 메이저면 정상 풀(스캠 아님)
    "So11111111111111111111111111111111111111112",  # SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",   # mSOL
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",  # stSOL
    "jupSoLaHXQiZZTSfEWMTRRgpnyFm8f6sZdosWBjx93v",   # jupSOL
    "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",  # jitoSOL
    "bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1",   # bSOL
}

if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 900:
    sys.exit("다른 인스턴스 실행 중")
open(LOCK, "w").write(str(os.getpid()))

# 풀 후보 추출
pools = []
for r in csv.DictReader(open(SCAN, encoding="utf-8")):
    if r["exists"] == "0":
        continue
    if r["owner_prog"] in NON_POOL or r["acct_type"] in NON_POOL_TYPE:
        continue
    pools.append(r["address"])

done = set()
if os.path.exists(DST):
    for r in csv.DictReader(open(DST, encoding="utf-8")):
        done.add(r["pool"])
pools = [p for p in pools if p not in done]
print(f"풀 후보 {len(pools)} (완료 {len(done)})", flush=True)

def batch(addrs):
    url = "https://api.dexscreener.com/latest/dex/pairs/solana/" + ",".join(addrs)
    for _ in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode()).get("pairs") or []
        except Exception:
            time.sleep(2)
    return None

FIELDS = ["pool", "verdict", "liquidity_usd", "scam_mint", "scam_sym", "quote_sym", "dex"]
out = open(DST, "a" if done else "w", newline="", encoding="utf-8")
w = csv.DictWriter(out, fieldnames=FIELDS)
if not done:
    w.writeheader()

from collections import Counter
stat = Counter()
try:
    for i in range(0, len(pools), 30):
        chunk = pools[i:i + 30]
        prs = batch(chunk)
        if prs is None:
            print(f"  배치 {i} 실패 — 스킵", flush=True)
            continue
        by_pool = {}
        for pr in prs:
            pa = pr.get("pairAddress")
            if pa:
                by_pool[pa] = pr
        for p in chunk:
            pr = by_pool.get(p)
            if pr is None:
                w.writerow({"pool": p, "verdict": "rug_completed", "liquidity_usd": 0})
                stat["rug_completed"] += 1
                continue
            liq = (pr.get("liquidity") or {}).get("usd") or 0
            bt = pr.get("baseToken") or {}
            qt = pr.get("quoteToken") or {}
            ba, qa = bt.get("address", ""), qt.get("address", "")
            dex = pr.get("dexId", "")
            if ba in MAJOR and qa in MAJOR:
                w.writerow({"pool": p, "verdict": "false_positive_major", "liquidity_usd": round(liq, 2),
                            "quote_sym": qt.get("symbol", ""), "dex": dex})
                stat["false_positive_major"] += 1
            else:
                scam_mint = qa if ba in MAJOR else ba
                scam_sym = qt.get("symbol", "") if ba in MAJOR else bt.get("symbol", "")
                quote_sym = bt.get("symbol", "") if ba in MAJOR else qt.get("symbol", "")
                v = "scam_pool_active" if liq > 0 else "rug_completed"
                w.writerow({"pool": p, "verdict": v, "liquidity_usd": round(liq, 2),
                            "scam_mint": scam_mint, "scam_sym": scam_sym[:20],
                            "quote_sym": quote_sym[:10], "dex": dex})
                stat[v] += 1
        out.flush()
        if (i // 30) % 30 == 0:
            open(LOCK, "w").write(str(os.getpid()))
            print(f"  {i+len(chunk)}/{len(pools)}  {dict(stat)}", flush=True)
        time.sleep(0.25)   # ~240 req/min < 300 한도
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: {dict(stat)}")
