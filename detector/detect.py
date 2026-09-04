# -*- coding: utf-8 -*-
"""Tier-1 규칙 기반 러그 탐지기 — mint 하나를 온체인 스냅샷으로 채점.
사용: python detect.py <mint_address>
검증된 신호(research/compare)만 사용, 고정밀 블록리스트 지향.
- 권한/공급: getAccountInfo (공개 RPC, 지금 가능)
- 홀더집중: getTokenLargestAccounts (Helius 키 있으면 사용, 없으면 시도/생략)
- 유동성: DexScreener
Helius 키: ~/.helius_key 파일이 있으면 자동 사용.
"""
import json, os, sys, urllib.request, urllib.error

MINT = sys.argv[1] if len(sys.argv) > 1 else None
if not MINT:
    sys.exit("사용법: python detect.py <mint_address>")

KEYPATH = os.path.expanduser("~/.helius_key")
HELIUS = open(KEYPATH).read().strip() if os.path.exists(KEYPATH) else None
RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS}" if HELIUS else "https://api.mainnet-beta.solana.com"
TOKEN2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
# 풀/소각 소유자 — 홀더집중 계산 시 제외 (유동성 락은 정상)
POOL_OWNERS = {"5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j",  # Raydium AMM v4
               "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium
               "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # Raydium CLMM
               "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX"}
BURN = {"11111111111111111111111111111111", "1nc1nerator11111111111111111111111111111111"}

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()).get("result")
    except urllib.error.HTTPError as e:
        return {"__err__": f"HTTP {e.code}"}
    except Exception as e:
        return {"__err__": str(e)[:60]}

def dexscreener(mint):
    url = f"https://api.dexscreener.com/tokens/v1/solana/{mint}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            prs = json.loads(r.read().decode())
        if not prs:
            return None
        best = max(prs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
        return {"liquidity_usd": (best.get("liquidity") or {}).get("usd") or 0,
                "pair": True, "dex": best.get("dexId")}
    except Exception:
        return None

# ── 1. 권한/공급/확장 (getAccountInfo) ──
info = rpc("getAccountInfo", [MINT, {"encoding": "jsonParsed"}])
signals, score, reasons = {}, 0, []
if not info or info.get("__err__") or not info.get("value"):
    err = (info or {}).get("__err__", "계정 없음/닫힘")
    print(f"⚠️ getAccountInfo 실패 또는 계정 닫힘 ({err}) — 완료된 러그일 수 있음(계정 소각)")
    signals["account_closed"] = True
    score += 40; reasons.append("계정 닫힘/조회불가 (완료된 러그 가능)")
    val = None
else:
    val = info["value"]
    owner = val.get("owner")
    parsed = (val.get("data") or {}).get("parsed") or {}
    inf = parsed.get("info") or {}
    is2022 = owner == TOKEN2022
    mint_auth = inf.get("mintAuthority")
    freeze_auth = inf.get("freezeAuthority")
    decimals = inf.get("decimals")
    supply = float(inf.get("supply") or 0)
    exts = [e.get("extension") for e in (inf.get("extensions") or [])]
    signals.update(is_token2022=is2022, mint_auth_live=bool(mint_auth),
                   freeze_auth_live=bool(freeze_auth), decimals=decimals, extensions=exts)
    print(f"토큰: {'Token-2022' if is2022 else 'SPL'}  decimals={decimals}  supply={supply:.0f}")
    print(f"권한: mint={'살아있음' if mint_auth else '소각'}  freeze={'살아있음' if freeze_auth else '소각'}")
    # ⚠️ 권한 생존은 점수화하지 않는다 — 우리 연구(research/compare): 정상이 오히려 권한 생존율
    #    더 높음(정상 8.9%/2.6% vs 러그 0%). 요즘 러그는 launchpad가 권한 자동소각.
    #    권한 생존을 위험으로 잡으면 USDC 등 정상을 오탐 → 고정밀 블록리스트에 역효과. 정보 표시만.
    RISKY_EXT = {"transferHook", "permanentDelegate", "transferFeeConfig"}
    bad = [e for e in exts if e in RISKY_EXT]
    if bad:
        score += 15; reasons.append(f"위험 확장: {bad}")
        print(f"⚠️ 위험 Token-2022 확장: {bad}")

# ── 2. 홀더 집중도 (getTokenLargestAccounts) — 최강 신호 ──
top1_pct = None
largest = rpc("getTokenLargestAccounts", [MINT])
if largest and not largest.get("__err__") and largest.get("value"):
    supply_res = rpc("getTokenSupply", [MINT])
    supply_ui = None
    if supply_res and not supply_res.get("__err__"):
        supply_ui = float((supply_res.get("value") or {}).get("uiAmount") or 0)
    accts = largest["value"]
    # 각 홀더 소유자 확인은 비용 큼 → 상위 잔고만으로 집중도(보수적: 풀 제외 없이 최대치)
    amts = sorted([float(a.get("uiAmount") or 0) for a in accts], reverse=True)
    if supply_ui and supply_ui > 0:
        top1_pct = 100 * amts[0] / supply_ui if amts else 0
        top10_pct = 100 * sum(amts[:10]) / supply_ui
        signals.update(top1_pct=round(top1_pct, 2), top10_pct=round(top10_pct, 2))
        print(f"홀더집중: top1={top1_pct:.1f}%  top10={top10_pct:.1f}%  (상위 {len(amts)}개 조회)")
        # 검증된 규칙 (research/compare)
        if top1_pct >= 99:
            score += 45; reasons.append(f"단일홀더 {top1_pct:.0f}% ≥99% (FPR 0.3%)")
        elif top1_pct >= 95:
            score += 40; reasons.append(f"단일홀더 {top1_pct:.0f}% ≥95% (FPR 1.1%)")
        elif top1_pct >= 90:
            score += 30; reasons.append(f"단일홀더 {top1_pct:.0f}% ≥90% (FPR 3.4%)")
else:
    err = (largest or {}).get("__err__", "?")
    print(f"홀더집중: 조회 실패 ({err}) — {'Helius 키 필요' if not HELIUS else 'RPC 제한'}")

# ── 3. 유동성 (DexScreener) ──
dex = dexscreener(MINT)
if dex is None:
    print("유동성: DexScreener 페어 없음 — 유동성 제거됨(완료 러그) 또는 미상장")
    signals["no_pair"] = True
    score += 20; reasons.append("DEX 페어 없음 (유동성 제거/미상장)")
else:
    liq = dex["liquidity_usd"]
    signals["liquidity_usd"] = round(liq, 2)
    print(f"유동성: ${liq:,.0f} ({dex['dex']})")
    if top1_pct is not None and top1_pct >= 90 and liq <= 100:
        score += 10; reasons.append("복합: 홀더≥90% AND 유동성≤$100 (FPR 0.6%)")

# ── 판정 (고정밀 블록리스트) ──
score = min(score, 100)
if (top1_pct is not None and top1_pct >= 95) or signals.get("account_closed") or \
   (top1_pct is not None and top1_pct >= 90 and signals.get("liquidity_usd", 1e9) <= 100):
    verdict = "🔴 BLOCK (고위험 — 자동 차단 권장)"
elif score >= 40:
    verdict = "🟠 WARN (의심 — 수동 검토)"
else:
    verdict = "🟢 LOW (뚜렷한 위험신호 없음)"

print("\n" + "=" * 56)
print(f"판정: {verdict}")
print(f"위험점수: {score}/100")
if reasons:
    print("근거:")
    for r in reasons:
        print(f"  • {r}")
if not HELIUS:
    print("\n💡 ~/.helius_key 를 설정하면 홀더집중(최강 신호)까지 채점됩니다.")
print("=" * 56)
