# -*- coding: utf-8 -*-
"""공개 스캠/제재 주소 데이터셋을 통합 스키마로 정규화한다.
출력 스키마: address, chain, category, source, label, detail, ref_date
"""
import csv, json, os, re
import xml.etree.ElementTree as ET
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "sources")
os.makedirs(OUT, exist_ok=True)

EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")

def classify(addr):
    if EVM_RE.match(addr):
        return "ETH"
    if addr.startswith(("bc1", "ltc1", "tb1")):
        return "BTC"
    if BASE58_RE.match(addr):
        n = len(addr)
        if addr.startswith("T") and n == 34:
            return "TRON"
        if addr.startswith("r") and 25 <= n <= 35:
            return "XRP"
        if 42 <= n <= 44:
            return "SOL"
        if 25 <= n <= 35:
            return "BTC_LIKE"
    if re.match(r"^0\.0\.\d+$", addr):
        return "HEDERA"
    return "OTHER"

def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writerows(rows)
    print(f"  -> {os.path.basename(path)}: {len(rows)} rows")

all_eth, all_sol = [], []

# ---------- 1. Chainabuse sitemap ----------
print("[1] Chainabuse sitemap")
addrs = set()
for fn in ("chainabuse_sitemap0.xml", "chainabuse_sitemap1.xml"):
    with open(os.path.join(RAW, fn), encoding="utf-8", errors="replace") as f:
        text = f.read()
    for m in re.finditer(r"chainabuse\.com/address/([^<]+)", text):
        addrs.add(m.group(1).strip())
print(f"  총 신고 주소 페이지: {len(addrs)}")
dist = Counter(classify(a) for a in addrs)
print(f"  체인 분포: {dict(dist)}")
ca_eth = [[a, "ETH", "community_reported", "chainabuse_sitemap", "reported", "", ""] for a in sorted(addrs) if classify(a) == "ETH"]
ca_sol = [[a, "SOL", "community_reported", "chainabuse_sitemap", "reported", "", ""] for a in sorted(addrs) if classify(a) == "SOL"]
write_rows(os.path.join(OUT, "chainabuse_reported_eth.csv"), ca_eth)
write_rows(os.path.join(OUT, "chainabuse_reported_sol.csv"), ca_sol)
all_eth += ca_eth
all_sol += ca_sol

# ---------- 2. OFAC SDN (program -> country) ----------
print("[2] OFAC SDN XML")
PROGRAM_THEME = {
    "DPRK": "North Korea", "DPRK2": "North Korea", "DPRK3": "North Korea",
    "DPRK4": "North Korea", "NKSPEA": "North Korea",
    "IRAN": "Iran", "IRAN-EO13876": "Iran", "IRAN-HR": "Iran", "IFSR": "Iran", "IRGC": "Iran",
    "RUSSIA-EO14024": "Russia", "PEESA-EO14039": "Russia",
    "UKRAINE-EO13661": "Russia", "UKRAINE-EO13662": "Russia", "UKRAINE-EO13685": "Russia",
    "MAGNIT": "Russia-related",
    "CYBER2": "Cybercrime", "CYBER3": "Cybercrime",
    "SDGT": "Terrorism financing",
    "SDNTK": "Narcotics", "ILLICIT-DRUGS-EO14059": "Narcotics",
}
ns = {"s": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML"}
sdn_path = os.path.join(RAW, "ofac_sdn.xml")
# 네임스페이스 자동 감지
head = open(sdn_path, encoding="utf-8", errors="replace").read(2000)
m = re.search(r'xmlns="([^"]+)"', head)
uri = m.group(1) if m else ""
tag = lambda t: f"{{{uri}}}{t}" if uri else t

ofac_rows = []
context = ET.iterparse(sdn_path, events=("end",))
for event, elem in context:
    if elem.tag == tag("sdnEntry"):
        programs = [p.text or "" for p in elem.iter(tag("program"))]
        ln = elem.find(tag("lastName"))
        fn_ = elem.find(tag("firstName"))
        name = " ".join(x.text for x in (fn_, ln) if x is not None and x.text)
        for idel in elem.iter(tag("id")):
            it = idel.find(tag("idType"))
            iv = idel.find(tag("idNumber"))
            if it is not None and iv is not None and it.text and it.text.startswith("Digital Currency Address"):
                asset = it.text.split("-")[-1].strip()
                addr = (iv.text or "").strip()
                themes = sorted({PROGRAM_THEME.get(p, p) for p in programs})
                ofac_rows.append([addr, classify(addr), f"sanctions:{asset}", "ofac_sdn",
                                  ";".join(programs), f"{name} | theme={'/'.join(themes)}", ""])
        elem.clear()
print(f"  OFAC 디지털화폐 주소 수: {len(ofac_rows)}")
with open(os.path.join(OUT, "ofac_sanctions_all.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "programs", "entity_theme", "ref_date"])
    w.writerows(ofac_rows)
print(f"  -> ofac_sanctions_all.csv: {len(ofac_rows)} rows")
ofac_eth = [r for r in ofac_rows if r[1] == "ETH"]
ofac_sol = [r for r in ofac_rows if r[1] == "SOL"]
all_eth += [[r[0], "ETH", "sanctions", "ofac_sdn", r[4], r[5], ""] for r in ofac_eth]
all_sol += [[r[0], "SOL", "sanctions", "ofac_sdn", r[4], r[5], ""] for r in ofac_sol]
print(f"  ETH: {len(ofac_eth)}, SOL: {len(ofac_sol)}")
# 0xB10C 교차검증
for code, fn2 in (("ETH", "ofac_eth.json"), ("SOL", "ofac_sol.json")):
    with open(os.path.join(RAW, fn2), encoding="utf-8") as f:
        ext = set(json.load(f))
    mine = {r[0] for r in ofac_rows if r[1] == code} if code == "ETH" else {r[0] for r in ofac_rows if r[1] == "SOL"}
    print(f"  교차검증 {code}: 0xB10C={len(ext)}, sdn.xml파싱(체인추정)={len(mine)}, 교집합={len(ext & mine)}")

# ---------- 3. ScamSniffer ----------
print("[3] ScamSniffer")
with open(os.path.join(RAW, "scamsniffer_address.json"), encoding="utf-8") as f:
    ss = json.load(f)
ss_rows = [[a.lower(), "ETH", "phishing_drainer", "scamsniffer", "phishing", "", ""] for a in ss]
write_rows(os.path.join(OUT, "scamsniffer_phishing_eth.csv"), ss_rows)
all_eth += ss_rows

# ---------- 4. MEW darklist ----------
print("[4] MEW darklist")
with open(os.path.join(RAW, "mew_addresses_darklist.json"), encoding="utf-8") as f:
    mew = json.load(f)
mew_rows = [[e["address"], "ETH", "scam_community_verified", "mew_ethereum_lists",
             "darklist", (e.get("comment") or "").replace("\n", " ")[:200], e.get("date", "")] for e in mew]
write_rows(os.path.join(OUT, "mew_darklist_eth.csv"), mew_rows)
all_eth += mew_rows

# ---------- 5. Forta ----------
print("[5] Forta labelled-datasets (2023 스냅샷)")
forta_rows = []
with open(os.path.join(RAW, "forta_phishing_scams.csv"), encoding="utf-8", errors="replace") as f:
    for row in csv.DictReader(f):
        forta_rows.append([row["address"], "ETH", "phishing", "forta_labelled_datasets",
                           row.get("etherscan_tag", ""), row.get("etherscan_labels", ""), "2023-01"])
with open(os.path.join(RAW, "forta_etherscan_malicious_labels.csv"), encoding="utf-8", errors="replace") as f:
    for row in csv.DictReader(f):
        forta_rows.append([row["banned_address"], "ETH", "malicious_label", "forta_labelled_datasets",
                           row.get("wallet_tag", ""), row.get("data_source", ""), "2023-01"])
with open(os.path.join(RAW, "forta_malicious_smart_contracts.csv"), encoding="utf-8", errors="replace") as f:
    for row in csv.DictReader(f):
        forta_rows.append([row["contract_address"], "ETH", "malicious_contract", "forta_labelled_datasets",
                           row.get("contract_tag", ""), row.get("contract_creator_etherscan_label", ""), "2023-01"])
write_rows(os.path.join(OUT, "forta_eth_malicious.csv"), forta_rows)
all_eth += forta_rows

# ---------- 6. SolRPDS ----------
print("[6] SolRPDS (Solana rug pulls)")
sol_rows = []
mints = set()
for fn3, year in (("2021.csv", "2021"), ("2022.csv", "2022"), ("2023.csv", "2023"), ("2024.csv", "2024")):
    p = os.path.join(RAW, "solrpds", fn3)
    with open(p, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            row = {(k or "").strip().upper(): v for k, v in row.items() if k}
            pool = (row.get("LIQUIDITY_POOL_ADDRESS") or "").strip()
            mint = (row.get("MINT") or "").strip()
            status = (row.get("INACTIVITY_STATUS") or "").strip()
            if pool:
                sol_rows.append([pool, "SOL", "rugpull_pool", "solrpds", status, f"mint={mint}", year])
            if mint and mint not in mints:
                mints.add(mint)
                sol_rows.append([mint, "SOL", "rugpull_token", "solrpds", status, f"pool={pool}", year])
write_rows(os.path.join(OUT, "solrpds_rugpull_sol.csv"), sol_rows)
all_sol += sol_rows

# ---------- 7. 마스터 병합 ----------
print("[7] master 파일")
def dedup(rows):
    seen, out2 = set(), []
    for r in rows:
        key = (r[0].lower() if r[0].startswith("0x") else r[0])
        if key in seen:
            continue
        seen.add(key)
        out2.append(r)
    return out2

for name, rows in (("master_ethereum.csv", all_eth), ("master_solana.csv", all_sol)):
    d = dedup(rows)
    write_rows(os.path.join(OUT, name), d)
    print(f"  {name}: 원본 {len(rows)} -> 중복제거 {len(d)}")
    print(f"  카테고리 분포: {dict(Counter(r[2] for r in d))}")
