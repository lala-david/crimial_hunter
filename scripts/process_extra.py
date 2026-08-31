# -*- coding: utf-8 -*-
"""신규 소스 정규화: ChainPatrol / AllenHark / SolPhishHunter / Japan MoF."""
import csv, json, os, re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "processed")

def cls(a):
    if re.match(r"^0x[0-9a-fA-F]{40}$", a): return "ETH"
    if a.startswith(("1", "3", "bc1")): return "BTC"
    if a.startswith("T") and len(a) == 34: return "TRON"
    if re.match(r"^[1-9A-HJ-NP-Za-km-z]{42,44}$", a): return "SOL"
    return "OTHER"

def save(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writerows(rows)
    print(f"-> {name}: {len(rows)} rows  {dict(Counter(r[1] for r in rows))}")

# ---- ChainPatrol ----
cp = []
with open(os.path.join(RAW, "chainpatrol_blocked.jsonl"), encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        cp.append([d["address"], d["chain"], "blocklist", "chainpatrol", "BLOCKED",
                   "", (d.get("blockedAt") or "")[:10]])
save("chainpatrol_blocked.csv", cp)

# ---- AllenHark (솔라나 Pump.fun 스캐머) ----
ah = []
with open(os.path.join(RAW, "allenhark_blacklist.jsonl"), encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        a = d.get("addr", "")
        if a:
            ah.append([a, cls(a), "scammer_pumpfun", "allenhark", "blacklist", "", ""])
save("allenhark_sol.csv", ah)

# ---- SolPhishHunter (학술 검증 phisher) ----
sp = set()
with open(os.path.join(RAW, "solphishhunter_final_results.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        raw = (r.get("phishers") or "")
        for x in re.split(r"[,\;\|\s]+", raw):
            x = x.strip().strip("[]'\"")
            if len(x) >= 32 and re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", x):
                sp.add(x)
sp_rows = [[a, "SOL", "phishing_verified", "solphishhunter", "academic", "IEEE TIFS 2026", ""] for a in sorted(sp)]
save("solphishhunter_sol.csv", sp_rows)

# ---- dawsbot/eth-labels phish-hack (이더리움, 최신) ----
el = []
with open(os.path.join(RAW, "ethlabels_phishhack.json"), encoding="utf-8") as f:
    for d in json.load(f):
        a = (d.get("address") or "").strip()
        if a:
            el.append([a, "ETH", "phishing", "eth_labels_dawsbot", "phish-hack",
                       (d.get("nameTag") or "")[:60], ""])
save("ethlabels_phishhack.csv", el)

# ---- Japan MoF (제재) ----
jp = []
with open(os.path.join(RAW, "opensanctions_jp_mof_sanctions.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["schema"] == "CryptoWallet":
            a = r["name"].strip()
            jp.append([a, cls(a), "sanctions", "jp_mof", "Japan MoF", "Japan", (r.get("last_seen") or "")[:10]])
save("jp_mof_sanctions.csv", jp)
