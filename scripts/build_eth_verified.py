# -*- coding: utf-8 -*-
"""Etherscan 검증 결과를 이더리움 마스터에 반영해 등급화한다.
출력: master_ethereum_verified.csv (전체+검증컬럼), master_ethereum_confirmed.csv (고신뢰)
"""
import csv, os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "ethereum")
VER = os.path.join(BASE, "ethereum", "verify")

# 거래소/합법 라벨 → 위양성 후보
EXCHANGE_HINTS = ("binance", "coinbase", "kraken", "okx", "deposit address", "gitcoin",
                  "uniswap", "gate.io", "kucoin", "bybit hot", "huobi", "bitfinex",
                  "crypto.com", "robinhood", "exchange")

# 검증 로드
ver = {}
with open(os.path.join(VER, "etherscan_verify.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        ver[r["address"].lower()] = (r.get("reputation", ""), r.get("labels", ""), r.get("nametag", ""))

# GoPlus 2차 검증 로드 — 강한 악성 플래그만 채택
# (blacklist_doubt=의심 수준, honeypot_related=연관성 추정, mixer=자체로는 스캠 아님 → 불채택)
GOPLUS_STRONG = {"phishing_activities", "stealing_attack", "blackmail_activities",
                 "cybercrime", "sanctioned"}
gp = {}
gpp = os.path.join(VER, "goplus_verify.csv")
if os.path.exists(gpp):
    with open(gpp, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            flags = set((r.get("flags") or "").split("|")) & GOPLUS_STRONG
            if flags:
                gp[r["address"].lower()] = "|".join(sorted(flags))

# 자금흐름 추적 데이터 — 피해자·거래소·경유지·IT worker 급여지갑 혼입 가능.
# 교차확인 집계에서 제외: Etherscan rep 2/3 없이는 confirmed 진입 불가.
TAINTED_TRACE = {"tayvano_lazarus", "tayvano_trace_extra"}

# 고신뢰 외부 소스 — 제재·발행사집행·전문큐레이션·수사 ground-truth.
# 커뮤니티 미검증 신고와 급이 다르므로 단일 소스여도 confirmed 자격.
HIGH_TRUST = {"ofac_sdn", "chainalysis_oracle", "revokecash",
              "ponzi_unica", "elementus_plustoken",
              "fbi_ic3_psa250226", "jp_mof",
              "opensanctions:il_nbctf", "opensanctions:us_fbi_lazarus",
              "usdt_banned", "usdc_banned"}

def tier(rep, labels, sources, addr):
    labs = (labels or "").lower()
    is_exch = any(h in labs for h in EXCHANGE_HINTS)
    src_set = set((sources or "").split("|"))
    if rep in ("2", "3"):
        return "CONFIRMED_MALICIOUS"          # Etherscan 공식 악성
    if rep == "0" and is_exch:
        return "EXCHANGE_FALSE_POSITIVE"      # 거래소/합법 → 제외 권장
    if src_set & HIGH_TRUST:
        return "CURATED_CONFIRMED"            # 제재·집행·전문큐레이션·수사 (단일이어도 고신뢰)
    if addr in gp:
        return "GOPLUS_CONFIRMED"             # GoPlus 독립 악성 라벨 (2차 검증)
    clean = [s for s in src_set if s not in TAINTED_TRACE]
    if len(clean) >= 2:
        return "CROSS_CONFIRMED"              # 다수 소스 교차확인 (추적 데이터 제외 기준)
    return "COMMUNITY_ONLY"                   # 커뮤니티 단일 신고(미검증)

rows = list(csv.DictReader(open(os.path.join(OUT, "master_ethereum.csv"), encoding="utf-8")))
out_rows = []
tiers = Counter()
for r in rows:
    a = r["address"].lower()
    rep, labels, nametag = ver.get(a, ("", "", ""))
    sc = int(r.get("source_count", 1))
    t = tier(rep, labels, r.get("sources", ""), a)
    tiers[t] += 1
    out_rows.append([r["address"], r["chain"], sc, r["sources"], r["categories"],
                     rep, labels, nametag, t])

hdr = ["address", "chain", "source_count", "sources", "categories",
       "etherscan_reputation", "etherscan_labels", "etherscan_nametag", "tier"]
with open(os.path.join(OUT, "master_ethereum_verified.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(out_rows)

# 고신뢰 확정 = Etherscan 악성 + 고신뢰큐레이션 + GoPlus 2차확정 + 교차확인 (거래소 위양성 제외)
conf = [r for r in out_rows if r[8] in ("CONFIRMED_MALICIOUS", "CURATED_CONFIRMED",
                                        "GOPLUS_CONFIRMED", "CROSS_CONFIRMED")]
with open(os.path.join(OUT, "master_ethereum_confirmed.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(conf)

# 참고 보관 = 커뮤니티 신고지만 미검증
comm = [r for r in out_rows if r[8] == "COMMUNITY_ONLY"]
with open(os.path.join(OUT, "archive_ethereum_community_unverified.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(comm)

# 최엄격 = Etherscan 공식 악성만
strict = [r for r in out_rows if r[8] == "CONFIRMED_MALICIOUS"]
with open(os.path.join(OUT, "master_ethereum_etherscan_confirmed.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(strict)

print(f"이더리움 전체: {len(out_rows)}")
print(f"등급 분포: {dict(tiers)}")
print(f"-> master_ethereum_confirmed.csv (고신뢰): {len(conf)}")
print(f"   그중 Etherscan 악성확정: {sum(1 for r in conf if r[8]=='CONFIRMED_MALICIOUS')}")
