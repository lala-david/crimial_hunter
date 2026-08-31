# -*- coding: utf-8 -*-
"""① DS2L/Poison-Hunter groundtruth — 주소오염 피싱 주소 (Etherscan+Forta 이중라벨, ETH)
   ② Phantom nft-blocklist — 솔라나 스캠 토큰 mint (지갑 아님 → 온체인 분류가 토큰으로 분리)
출력: sources/poisonhunter_eth.csv, sources/phantom_sol.csv
"""
import csv, os, re, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "sources")

def download(url, dst, min_bytes=1000):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dst + ".tmp", "wb") as f:
            f.write(r.read())
        if os.path.getsize(dst + ".tmp") > min_bytes:
            os.replace(dst + ".tmp", dst)
            return True
    except Exception as e:
        print(f"  (다운로드 실패, 기존 사용: {e})")
    return False

def save(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writerows(rows)
    print(f"-> {name}: {len(rows)}개")

# ① Poison-Hunter (ETH 주소오염 피싱, 이중라벨 groundtruth)
download("https://raw.githubusercontent.com/DS2L/Poison-Hunter/main/phishing_address_groundtruth.txt",
         os.path.join(RAW, "poisonhunter_groundtruth.txt"))
ETH = re.compile(r"^0x[0-9a-fA-F]{40}$")
seen, rows = set(), []
with open(os.path.join(RAW, "poisonhunter_groundtruth.txt"), encoding="utf-8") as f:
    for line in f:
        a = line.strip().lower()
        if ETH.match(a) and a not in seen:
            seen.add(a)
            rows.append([a, "ETH", "address_poisoning", "poison_hunter",
                         "Etherscan+Forta 이중라벨", "CCS2024 groundtruth", ""])
save("poisonhunter_eth.csv", rows)

# ② Phantom nft-blocklist (SOL 스캠 토큰 mint)
download("https://raw.githubusercontent.com/phantom/blocklist/master/nft-blocklist.yaml",
         os.path.join(RAW, "phantom_nft_blocklist.yaml"))
B58 = re.compile(r"mint:\s*([1-9A-HJ-NP-Za-km-z]{32,44})")
seen, rows = set(), []
with open(os.path.join(RAW, "phantom_nft_blocklist.yaml"), encoding="utf-8") as f:
    for line in f:
        m = B58.search(line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            rows.append([m.group(1), "SOL", "scam_token", "phantom_blocklist",
                         "blocked mint", "Phantom 큐레이션", ""])
save("phantom_sol.csv", rows)
