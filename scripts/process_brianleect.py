# -*- coding: utf-8 -*-
"""brianleect/etherscan-labels 라벨 덤프에서 악성 후보만 추출.
label 기준 + name(nametag) 키워드 기준. 최종 confirmed 여부는 뒷단 Etherscan 검증(rep 2/3)이 결정.
출력: sources/brianleect_malicious_eth.csv
"""
import csv, json, os, re, urllib.request
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "sources")

URL = "https://raw.githubusercontent.com/brianleect/etherscan-labels/main/data/etherscan/combined/combinedAllLabels.json"
DST = os.path.join(RAW, "brianleect_eth_labels.json")

MAL_LABELS = {"phish-hack", "heist", "exploit", "ofac-sanctioned", "ofac-sanctions-lists",
              "take-action", "blocked", "hacked", "cryptopia-hack", "upbit-hack",
              "bybit-exploit", "wazirx-exploit", "stake.com-hack", "ronin-bridge",
              "kucoin-hack", "phishing", "scam", "fake_phishing", "compromised"}
NAME_RE = re.compile(r"exploit|hacker|hack\b|phish|fake_phish|drainer|scam|rugpull|"
                     r"ponzi|heist|stealer|malicious|blackmail|sanctioned|lazarus", re.I)
# 정상인데 걸릴 수 있는 것 배제 (예: "Anti-Phishing", 정상 서비스)
NEG_RE = re.compile(r"anti-phish|phishing.?report|hackathon|hacker.?house|hackerlink", re.I)

try:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(DST + ".tmp", "wb") as f:
        f.write(r.read())
    if os.path.getsize(DST + ".tmp") > 500_000:
        os.replace(DST + ".tmp", DST)
        print("  brianleect 최신 반영")
except Exception as e:
    print(f"  (brianleect 갱신 실패, 기존 사용: {e})")

data = json.load(open(DST, encoding="utf-8"))
rows = []
reason = Counter()
for addr, meta in data.items():
    a = addr.lower()
    if not re.match(r"^0x[0-9a-fA-F]{40}$", a):
        continue
    name = meta.get("name") or ""
    labels = set(meta.get("labels") or [])
    hit_label = labels & MAL_LABELS
    hit_name = NAME_RE.search(name) and not NEG_RE.search(name)
    if not hit_label and not hit_name:
        continue
    cat = "sanctions" if (labels & {"ofac-sanctioned", "ofac-sanctions-lists"}) else \
          "exploit" if (labels & {"heist", "exploit"} or re.search(r"exploit|heist", name, re.I)) else \
          "phishing"
    rows.append([a, "ETH", cat, "brianleect_labels",
                 "|".join(sorted(hit_label))[:40] or "nametag", name[:60], ""])
    reason["label" if hit_label else "name"] += 1

with open(os.path.join(OUT, "brianleect_malicious_eth.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(rows)
print(f"-> brianleect_malicious_eth.csv: {len(rows)}개  (근거 {dict(reason)})")
print(f"   카테고리: {dict(Counter(r[2] for r in rows))}")
