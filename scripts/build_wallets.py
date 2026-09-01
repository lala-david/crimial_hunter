# -*- coding: utf-8 -*-
"""솔라나 '지갑' 전용 마스터 생성 — 토큰/풀 제외.
온체인 분류(sol_types_*.csv) 반영. 미분류는 소스 기본값 적용.
출력: master_solana_wallets.csv (지갑), master_solana_tokens.csv (토큰/풀)
"""
import csv, os
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "sources")
VER = os.path.join(BASE, "solana", "verify")
OUT = os.path.join(BASE, "solana")

# base58 32바이트 유효성 — 무효 pubkey(0x혼입·체크섬 미달) 노이즈 배제
_ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_IDX = {c: i for i, c in enumerate(_ALPH)}

def valid_pubkey(s):
    if not (32 <= len(s) <= 44):
        return False
    n = 0
    for c in s:
        if c not in _IDX:
            return False
        n = n * 58 + _IDX[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return len(b"\x00" * (len(s) - len(s.lstrip("1"))) + body) == 32

# 지갑 소스(기본 wallet) / 토큰·풀 소스(기본 token)
WALLET_SOURCES = [
    "chainabuse_crawl_SOL.csv", "chainabuse_desc_sol.csv", "allenhark_sol.csv",
    "chainpatrol_blocked.csv", "solphishhunter_sol.csv", "silent_killer_sol.csv",
    "graphsense_sol.csv",
    "tayvano_lazarus.csv", "kismp_defihack.csv", "rugcheck_creator_sol.csv",
    "solana_frozen_stablecoin.csv", "rekt_attacker.csv", "defi_rekt_attacker.csv",
    "solanafm_flagged.csv",
]  # 휴리스틱 제외: jcb07(BFS), midsummer(wash-trading), crimewallets(aged-wallet 매물) 는 수집 안 함
# ofac SOL은 ofac_sanctions_all.csv에서, jcb07은 아래 별도
# 토큰 소스(기본 token): Phantom mint = 스캠 토큰, 지갑 아님
TOKEN_SOURCES = ["solrpds_rugpull_sol.csv", "jupiter_banned_sol.csv", "phantom_sol.csv"]

# 온체인 분류 로드
types = {}
for f in ("sol_types_curated.csv", "sol_types_jcb07.csv", "sol_types_new.csv"):
    p = os.path.join(VER, f)
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            types[r["address"]] = r["type"]
print(f"온체인 분류 로드: {len(types)}개 ({dict(Counter(types.values()))})")

def is_wallet(addr, default_wallet):
    t = types.get(addr)
    if t is None:
        return default_wallet          # 미분류 → 소스 기본값
    return t in ("WALLET", "EMPTY")

# 집계
def _new():
    return {"cat": set(), "src": set(), "lbl": set()}
agg = defaultdict(_new)
addr_of = {}
dates = {}

def add(path, default_wallet, want_wallet):
    p = os.path.join(SRC, path)
    if not os.path.exists(p):
        print(f"  (없음) {path}"); return 0
    n = 0
    for r in csv.DictReader(open(p, encoding="utf-8")):
        a = (r.get("address") or "").strip()
        if not a or (r.get("chain") or "") != "SOL":
            continue
        # 노이즈 배제: base58 32바이트 유효성 미달(0x혼입·체크섬 실패) 제거
        if not valid_pubkey(a):
            continue
        if is_wallet(a, default_wallet) != want_wallet:
            continue
        e = agg[a]; addr_of[a] = a
        if r.get("category"): e["cat"].add(r["category"].split(":")[0] if ":" in r["category"] else r["category"])
        if r.get("source"): e["src"].add(r["source"])
        if r.get("label"): e["lbl"].add(r["label"][:30])
        d = (r.get("ref_date") or "")
        if d and d > dates.get(a, ""): dates[a] = d
        n += 1
    return n

# 저신뢰(대량 후보) 소스 — 고신뢰 세트에서 제외
LOWCONF = {"jcb07_bfs", "midsummer_meme"}

def dump(name, highconf_only=False):
    rows = []
    for a, e in agg.items():
        srcs = e["src"]
        if highconf_only and not (srcs - LOWCONF):
            continue   # 저신뢰 소스에만 있는 주소는 제외
        use = (srcs - LOWCONF) if highconf_only else srcs
        rows.append([a, "SOL", len(use), "|".join(sorted(use)),
                     "|".join(sorted(e["cat"]))[:150], types.get(a, "unclassified"), dates.get(a, "")])
    rows.sort(key=lambda x: (-x[2], x[0]))
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "source_count", "sources", "categories", "onchain_type", "ref_date"])
        w.writerows(rows)
    print(f"[{name}] {len(rows)}개")
    print(f"   온체인타입: {dict(Counter(types.get(r[0],'unclassified') for r in rows))}")
    print(f"   소스: {dict(Counter(s for r in rows for s in r[3].split('|')))}")
    return rows

# ---- 지갑 마스터 ----
print("\n=== 지갑(WALLET) 마스터 ===")
total = 0
for src in WALLET_SOURCES:
    total += add(src, default_wallet=True, want_wallet=True)
# ofac SOL
p = os.path.join(SRC, "ofac_sanctions_all.csv")
if os.path.exists(p):
    for r in csv.DictReader(open(p, encoding="utf-8")):
        a = (r.get("address") or "").strip()
        if r.get("chain") == "SOL" and valid_pubkey(a) and is_wallet(a, True):
            e = agg[a]; addr_of[a] = a
            e["src"].add("ofac_sdn"); e["cat"].add("sanctions")
# (jcb07 BFS 크롤 제외 — 휴리스틱)
dump("master_solana_wallets.csv")

# ---- 토큰/풀 마스터 (분리 보관) ----
print("\n=== 토큰/풀 마스터 (지갑 아님, 분리) ===")
agg.clear(); addr_of.clear(); dates.clear()
for src in TOKEN_SOURCES:
    add(src, default_wallet=False, want_wallet=False)
# 지갑소스 중 온체인 TOKEN으로 판명된 것도 토큰파일로
for src in WALLET_SOURCES:
    add(src, default_wallet=True, want_wallet=False)
dump("master_solana_tokens.csv")
