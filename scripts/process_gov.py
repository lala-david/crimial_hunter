# -*- coding: utf-8 -*-
"""정부·사법기관(FBI IC3, OpenSanctions) 소스를 통합하고 국가별 카테고리를 부여한다."""
import csv, json, os, re
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "processed")

EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
B58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")

def classify(a):
    if EVM_RE.match(a):
        return "ETH"
    if a.startswith("bc1") or (a.startswith(("1", "3")) and 25 <= len(a) <= 35):
        return "BTC"
    if a.startswith("T") and len(a) == 34:
        return "TRON"
    if a.startswith(("L", "M", "ltc1")):
        return "LTC"
    if a.startswith("X") and len(a) == 34:
        return "DASH"
    if a.startswith("r") and 25 <= len(a) <= 35:
        return "XRP"
    if a.startswith("bnb"):
        return "BNB"
    if B58_RE.match(a) and 42 <= len(a) <= 44:
        return "SOL"
    return "OTHER"

rows_all = []   # 통합 정부 소스 행: address, chain, category, source, jurisdiction, detail, ref_date

# ---------- FBI IC3 PSA250226 (Bybit / North Korea Lazarus) ----------
p = os.path.join(RAW, "ic3_bybit_eth.txt")
n = 0
with open(p, encoding="utf-8") as f:
    for line in f:
        a = line.strip()
        if a:
            rows_all.append([a, classify(a), "state_actor_theft", "fbi_ic3_psa250226",
                             "North Korea", "Bybit hack / TraderTraitor(Lazarus)", "2025-02-26"])
            n += 1
print(f"[FBI IC3 PSA250226] {n} ETH 주소")

# ---------- OpenSanctions datasets ----------
OS_META = {
    "opensanctions_us_fbi_lazarus_crypto.csv": ("state_actor_theft", "opensanctions:us_fbi_lazarus", "North Korea", "FBI Lazarus (Stake.com 등)"),
    "opensanctions_il_mod_crypto.csv":         ("sanctions_terror", "opensanctions:il_nbctf",     "Israel(NBCTF)", "이스라엘 테러자금 지정 지갑"),
    "opensanctions_ransomwhere.csv":           ("ransomware",       "opensanctions:ransomwhere",  "Global", "ransomwhe.re 랜섬웨어 결제 주소"),
}
for fn, (cat, src, juris, detail) in OS_META.items():
    cnt = 0
    with open(os.path.join(RAW, fn), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["schema"] != "CryptoWallet":
                continue
            addr = r["name"].strip()
            if not addr:
                continue
            rows_all.append([addr, classify(addr), cat, src, juris, detail, (r.get("last_seen") or "")[:10]])
            cnt += 1
    print(f"[{src}] {cnt} 주소")

# ---------- 저장: 정부 소스 통합 ----------
gov_path = os.path.join(OUT, "gov_law_enforcement_all.csv")
with open(gov_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "jurisdiction", "detail", "ref_date"])
    w.writerows(rows_all)
print(f"-> gov_law_enforcement_all.csv: {len(rows_all)} rows")
print("   체인 분포:", dict(Counter(r[1] for r in rows_all)))

# ---------- OFAC 국가별 분해 (기존 ofac_sanctions_all.csv 활용) ----------
ofac_path = os.path.join(OUT, "ofac_sanctions_all.csv")
by_country = defaultdict(list)
if os.path.exists(ofac_path):
    with open(ofac_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            theme = ""
            m = re.search(r"theme=([^|]+)", r.get("entity_theme", ""))
            if m:
                theme = m.group(1).strip()
            by_country[theme or "Unspecified"].append(r)
    print("\n[OFAC 국가/테마별 주소 수]")
    for k in sorted(by_country, key=lambda x: -len(by_country[x])):
        print(f"   {k}: {len(by_country[k])}")

# ---------- master에 SOL/ETH 정부소스 병합 ----------
def load_master(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return [], set()
    with open(p, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keys = {(r["address"].lower() if r["address"].startswith("0x") else r["address"]) for r in rows}
    return rows, keys

for chain_code, master_name in (("ETH", "master_ethereum.csv"), ("SOL", "master_solana.csv")):
    rows, keys = load_master(master_name)
    added = 0
    for r in rows_all:
        if r[1] != chain_code:
            continue
        key = r[0].lower() if r[0].startswith("0x") else r[0]
        if key in keys:
            continue
        keys.add(key)
        rows.append({"address": r[0], "chain": chain_code, "category": r[2],
                     "source": r[3], "label": r[4], "detail": r[5], "ref_date": r[6]})
        added += 1
    with open(os.path.join(OUT, master_name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n[{master_name}] 정부소스 {added}개 추가 -> 총 {len(rows)}개")
    print("   카테고리:", dict(Counter(r["category"] for r in rows)))
