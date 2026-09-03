# -*- coding: utf-8 -*-
"""솔라나 토큰 온체인 스캔 + 신고 데이터 조인 → 정확한 카테고리 체계.
축1: 계정 유형(토큰mint / 유동성풀 / 닫힘 / 지갑·기타)
축2: 권한 상태(mint/freeze authority, Token-2022 확장) — mint 한정
축3: 소스 신고 카테고리
"""
import csv, os
from collections import Counter

D = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(D))

scan = {r["address"]: r for r in csv.DictReader(open(os.path.join(D, "..", "data", "sol_onchain_scan.csv"), encoding="utf-8"))}
toks = list(csv.DictReader(open(os.path.join(BASE, "solana", "master_solana_tokens.csv"), encoding="utf-8")))
n = len(toks)
scanned = sum(1 for t in toks if t["address"] in scan)
print(f"=== 솔라나 토큰 전체 카테고리 분석 ===")
print(f"토큰 {n} / 스캔완료 {scanned} ({100*scanned/n:.0f}%)\n")

POOL = {"RAYDIUM_AMM", "RAYDIUM_CPMM", "ORCA_WHIRLPOOL", "METEORA_DLMM", "PUMP_FUN"}

def bucket(t):
    s = scan.get(t["address"])
    if not s:
        return "미스캔"
    if s["exists"] == "0" or s["acct_type"] == "CLOSED":
        return "계정닫힘(완료러그/드레인)"
    prog = s["owner_prog"]
    atype = s["acct_type"]
    if atype == "mint" and prog == "SPL_TOKEN":
        return "토큰mint(SPL)"
    if atype == "mint" and prog == "TOKEN_2022":
        return "토큰mint(Token-2022)"
    if prog in POOL:
        return f"유동성풀({prog})"
    if prog == "SYSTEM":
        return "지갑(System)"
    return f"기타({prog})"

# 축1: 계정 유형
print("[축1 — 계정 유형]")
b1 = Counter(bucket(t) for t in toks)
for k, v in b1.most_common():
    print(f"   {v:7} ({100*v/n:5.1f}%)  {k}")

# 축2: 토큰 mint의 권한 상태
mints = [t for t in toks if bucket(t).startswith("토큰mint")]
if mints:
    print(f"\n[축2 — 토큰 mint {len(mints)}개의 권한/함정]")
    ma = sum(1 for t in mints if scan[t["address"]]["mint_auth"] == "1")
    fa = sum(1 for t in mints if scan[t["address"]]["freeze_auth"] == "1")
    t22 = sum(1 for t in mints if scan[t["address"]]["owner_prog"] == "TOKEN_2022")
    print(f"   mint authority 활성(무한발행 가능): {ma} ({100*ma/len(mints):.1f}%)")
    print(f"   freeze authority 활성(허니팟 가능): {fa} ({100*fa/len(mints):.1f}%)")
    print(f"   Token-2022(확장 함정 가능): {t22} ({100*t22/len(mints):.1f}%)")
    # Token-2022 확장 종류
    ext = Counter()
    for t in mints:
        for e in (scan[t["address"]]["token2022_ext"] or "").split("|"):
            if e:
                ext[e] += 1
    if ext:
        print("   Token-2022 확장 종류:")
        for e, c in ext.most_common(8):
            print(f"      {c:5}  {e}")

# 축3: 소스 신고 카테고리 × 계정유형
print("\n[축3 — 신고 카테고리 × 계정유형 (상위)]")
cross = Counter()
for t in toks:
    b = bucket(t)
    for c in t["categories"].split("|"):
        cross[(c, b)] += 1
for (cat, b), v in cross.most_common(15):
    print(f"   {v:7}  {cat:22} → {b}")

# 최종 카테고리 요약
print("\n[★ 최종 카테고리 체계 제안]")
alive_mint = sum(1 for t in toks if bucket(t).startswith("토큰mint"))
pools = sum(1 for t in toks if bucket(t).startswith("유동성풀"))
closed = b1.get("계정닫힘(완료러그/드레인)", 0)
print(f"   1. 스캠 토큰 mint (살아있음): {alive_mint}")
print(f"   2. 러그풀 유동성 풀: {pools}")
print(f"   3. 완료 러그(계정 닫힘): {closed}")
print(f"   4. 기타(지갑/컨트랙트): {n - alive_mint - pools - closed - b1.get('미스캔',0)}")
