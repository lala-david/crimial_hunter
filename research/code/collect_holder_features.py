# -*- coding: utf-8 -*-
"""논문 기반 온체인 feature 직접 계산 (leakage 없음).
Mazorra HHI + 홀더집중도(top1/top10/top20) — getTokenLargestAccounts로 실측.
커브 PDA/풀 vault 제외(논문 지적). RugCheck score 안 씀.
사용법: python collect_holder_features.py <mint목록.txt> <출력.csv> <label>
"""
import csv, json, os, sys, time, urllib.request

SRC, DST, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
LOCK = DST + ".lock"
RPC = "https://api.mainnet-beta.solana.com"
# 커브/풀/시스템 프로그램 소유 계정은 홀더 집계에서 제외 (개발자 물량 아님)
POOL_OWNERS = {
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  # pump.fun bonding curve
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",  # Raydium CPMM
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",   # Orca
}

if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 900:
    sys.exit("다른 인스턴스 실행 중")
open(LOCK, "w").write(str(os.getpid()))

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    delay = 1.5
    for _ in range(6):
        try:
            req = urllib.request.Request(RPC, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            if "result" in d:
                return d["result"]
            time.sleep(delay); delay = min(20, delay * 1.7)
        except Exception:
            time.sleep(delay); delay = min(20, delay * 1.7)
    return None

FIELDS = ["mint", "label", "status", "supply", "decimals", "n_top_holders",
          "top1_pct", "top5_pct", "top10_pct", "top20_pct", "hhi_top20",
          "mint_auth_live", "freeze_auth_live", "is_token2022", "n_extensions"]

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
    for i, mint in enumerate(targets):
        # mint 계정 파싱 (권한·supply·decimals·Token-2022 확장) — 논문의 Cernera/From Hype feature
        acc = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        av = (acc or {}).get("value")
        if not av:
            w.writerow({"mint": mint, "label": LABEL, "status": "no_account"}); stat["no_account"] += 1
            time.sleep(0.15); continue
        owner_prog = av.get("owner", "")
        is_t22 = 1 if owner_prog == "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb" else 0
        info = ((av.get("data") or {}).get("parsed") or {}).get("info", {})
        mint_auth = 1 if info.get("mintAuthority") else 0
        freeze_auth = 1 if info.get("freezeAuthority") else 0
        exts = info.get("extensions") or []
        n_ext = len(exts) if isinstance(exts, list) else 0
        total = float(info.get("supply") or 0)
        dec = info.get("decimals", "")
        if total <= 0:
            w.writerow({"mint": mint, "label": LABEL, "status": "zero_supply", "supply": total,
                        "decimals": dec, "mint_auth_live": mint_auth, "freeze_auth_live": freeze_auth,
                        "is_token2022": is_t22, "n_extensions": n_ext}); stat["zero_supply"] += 1
            time.sleep(0.15); continue
        largest = rpc("getTokenLargestAccounts", [mint])
        vals = (largest or {}).get("value") or []
        base = {"mint_auth_live": mint_auth, "freeze_auth_live": freeze_auth,
                "is_token2022": is_t22, "n_extensions": n_ext}
        if not vals:
            w.writerow({"mint": mint, "label": LABEL, "status": "empty",
                        "supply": total, "decimals": dec, **base}); stat["empty"] += 1
            time.sleep(0.15); continue
        # 각 최대 계정의 owner를 조회해 풀/커브 제외 (top 몇 개만)
        amts = []
        for acc in vals:
            amts.append(float(acc.get("amount") or 0))
        # 풀 vault 판별: 1위가 supply의 대부분이고 owner가 풀이면 제외 — owner 조회
        accounts = [acc["address"] for acc in vals[:5]]
        infos = rpc("getMultipleAccounts", [accounts, {"encoding": "jsonParsed"}]) if accounts else None
        pool_idx = set()
        if infos and infos.get("value"):
            for j, info in enumerate(infos["value"]):
                if not info:
                    continue
                owner = ((info.get("data") or {}).get("parsed") or {}).get("info", {}).get("owner", "")
                if owner in POOL_OWNERS:
                    pool_idx.add(j)
        # 풀 제외한 홀더 amounts
        holder_amts = [a for j, a in enumerate(amts) if j not in pool_idx]
        if not holder_amts:
            holder_amts = amts
        holder_amts.sort(reverse=True)
        def pct(k):
            return round(100 * sum(holder_amts[:k]) / total, 4)
        hhi = round(sum((a / total) ** 2 for a in holder_amts), 6)  # top20 근사 HHI
        w.writerow({"mint": mint, "label": LABEL, "status": "ok", "supply": total, "decimals": dec,
                    "n_top_holders": len(holder_amts), "top1_pct": pct(1), "top5_pct": pct(5),
                    "top10_pct": pct(10), "top20_pct": pct(20), "hhi_top20": hhi, **base})
        stat["ok"] += 1
        if (i + 1) % 50 == 0:
            out.flush(); open(LOCK, "w").write(str(os.getpid()))
            print(f"  {i+1}/{len(targets)}  {dict(stat)}", flush=True)
        time.sleep(0.2)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: {dict(stat)}")
