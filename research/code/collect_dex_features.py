# -*- coding: utf-8 -*-
"""DexScreener 거래패턴 feature 수집 (RPC 우회, 홀더 없이) — Catching the Rug 방식.
feature: liquidity, volume24h, txns24h(buys/sells), buy_sell_ratio, priceChange, fdv, age_days.
+ 온체인 검증 라벨: DexScreener 무응답/유동성0 = 확정 러그(사후 검증).
사용법: python collect_dex_features.py <mint목록> <출력.csv> <label>
"""
import csv, json, os, sys, time, urllib.request

SRC, DST, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
LOCK = DST + ".lock"
NOW = time.time()
if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 900:
    sys.exit("실행중")
open(LOCK, "w").write(str(os.getpid()))

def batch(addrs):
    url = "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(addrs)
    for _ in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(2)
    return None

FIELDS = ["mint", "label", "status", "liquidity_usd", "volume24h", "buys24h", "sells24h",
          "buy_sell_ratio", "price_change_24h", "fdv", "age_days", "dex"]
done = set()
if os.path.exists(DST):
    for r in csv.DictReader(open(DST, encoding="utf-8")):
        done.add(r["mint"])
targets = [l.strip() for l in open(SRC, encoding="utf-8") if l.strip() and l.strip() not in done]
print(f"수집 {len(targets)} (label={LABEL}, 완료 {len(done)})", flush=True)

out = open(DST, "a" if done else "w", newline="", encoding="utf-8")
w = csv.DictWriter(out, fieldnames=FIELDS)
if not done:
    w.writeheader()

from collections import Counter
stat = Counter()
try:
    for i in range(0, len(targets), 30):
        chunk = targets[i:i + 30]
        prs = batch(chunk)
        if prs is None:
            print(f"  배치 {i} 실패", flush=True); continue
        # 토큰별 최대유동성 pair
        best = {}
        for p in (prs if isinstance(prs, list) else []):
            bt = (p.get("baseToken") or {}).get("address", "")
            liq = (p.get("liquidity") or {}).get("usd") or 0
            if bt and (bt not in best or liq > (best[bt].get("liquidity") or {}).get("usd", 0)):
                best[bt] = p
        for m in chunk:
            p = best.get(m)
            if p is None:
                # DexScreener 무응답 = 페어 없음 = 유동성 완전 제거(확정 러그) 또는 미상장
                w.writerow({"mint": m, "label": LABEL, "status": "no_pair"}); stat["no_pair"] += 1
                continue
            liq = (p.get("liquidity") or {}).get("usd") or 0
            vol = (p.get("volume") or {}).get("h24") or 0
            tx = (p.get("txns") or {}).get("h24") or {}
            buys, sells = tx.get("buys") or 0, tx.get("sells") or 0
            pc = (p.get("priceChange") or {}).get("h24") or 0
            created = p.get("pairCreatedAt")
            age = round((NOW - created / 1000) / 86400, 2) if created else ""
            w.writerow({"mint": m, "label": LABEL, "status": "ok",
                        "liquidity_usd": round(liq, 2), "volume24h": round(vol, 2),
                        "buys24h": buys, "sells24h": sells,
                        "buy_sell_ratio": round(buys / max(sells, 1), 3),
                        "price_change_24h": pc, "fdv": p.get("fdv") or "",
                        "age_days": age, "dex": p.get("dexId", "")})
            stat["ok"] += 1
        out.flush()
        if (i // 30) % 20 == 0:
            open(LOCK, "w").write(str(os.getpid()))
            print(f"  {i+len(chunk)}/{len(targets)}  {dict(stat)}", flush=True)
        time.sleep(0.25)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: {dict(stat)}")
