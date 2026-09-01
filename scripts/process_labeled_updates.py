# -*- coding: utf-8 -*-
"""라이브 라벨 소스 재수집 + 정규화 — ScamSniffer, MEW darklist.
기존 소스명·스키마 유지(중복 집계 방지). 다운로드 실패 시 기존 raw 유지.
"""
import csv, json, os, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "sources")

def download(url, dst, min_bytes=1000):
    tmp = dst + ".tmp"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        f.write(r.read())
    n = os.path.getsize(tmp)
    if n < min_bytes or (os.path.exists(dst) and n < os.path.getsize(dst) * 0.5):
        os.remove(tmp)
        raise RuntimeError(f"다운로드 크기 이상({n}B) — 기존 유지: {url}")
    os.replace(tmp, dst)
    print(f"  {os.path.basename(dst)}: {n:,}B")

def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writerows(rows)
    print(f"-> {os.path.basename(path)}: {len(rows)} rows")

# ---- ScamSniffer (드레이너/피싱 라벨) ----
try:
    download("https://raw.githubusercontent.com/scamsniffer/scam-database/main/blacklist/address.json",
             os.path.join(RAW, "scamsniffer_address.json"))
except Exception as e:
    print(f"  (scamsniffer 다운로드 실패, 기존 raw 사용: {e})")
# combined.json = 피싱 도메인별 드레이너 주소 매핑, all.json = 전체 통합(address 4,600+)
for fn in ("combined.json", "all.json"):
    try:
        download(f"https://raw.githubusercontent.com/scamsniffer/scam-database/main/blacklist/{fn}",
                 os.path.join(RAW, f"scamsniffer_{fn}"), min_bytes=50000)
    except Exception as e:
        print(f"  (scamsniffer {fn} 다운로드 실패, 기존 raw 사용: {e})")

import re as _re
_ETH = _re.compile(r"^0x[0-9a-fA-F]{40}$")
addr_domain = {}   # addr -> 첫 등장 도메인
ss = json.load(open(os.path.join(RAW, "scamsniffer_address.json"), encoding="utf-8"))
for a in ss:
    if _ETH.match(a):
        addr_domain.setdefault(a.lower(), "")
# all.json의 address 리스트 (address.json보다 완전)
ap = os.path.join(RAW, "scamsniffer_all.json")
if os.path.exists(ap):
    alld = json.load(open(ap, encoding="utf-8"))
    for a in (alld.get("address") or []):
        if isinstance(a, str) and _ETH.match(a):
            addr_domain.setdefault(a.lower(), "")
cp = os.path.join(RAW, "scamsniffer_combined.json")
if os.path.exists(cp):
    for domain, addrs in json.load(open(cp, encoding="utf-8")).items():
        for a in (addrs if isinstance(addrs, list) else [addrs]):
            if isinstance(a, str) and _ETH.match(a):
                addr_domain.setdefault(a.lower(), domain[:50])
write_rows(os.path.join(OUT, "scamsniffer_phishing_eth.csv"),
           [[a, "ETH", "phishing_drainer", "scamsniffer", "phishing", dom, ""]
            for a, dom in sorted(addr_domain.items())])

# ---- MEW darklist (커뮤니티 검증 스캠 라벨) ----
try:
    download("https://raw.githubusercontent.com/MyEtherWallet/ethereum-lists/master/src/addresses/addresses-darklist.json",
             os.path.join(RAW, "mew_addresses_darklist.json"))
except Exception as e:
    print(f"  (MEW 다운로드 실패, 기존 raw 사용: {e})")
mew = json.load(open(os.path.join(RAW, "mew_addresses_darklist.json"), encoding="utf-8"))
write_rows(os.path.join(OUT, "mew_darklist_eth.csv"),
           [[e["address"], "ETH", "scam_community_verified", "mew_ethereum_lists",
             "darklist", (e.get("comment") or "").replace("\n", " ")[:200], e.get("date", "")] for e in mew])
