# -*- coding: utf-8 -*-
"""Etherscan getaddresstag로 ETH 주소를 대량 검증/보강.
사용법: python verify_etherscan.py <입력csv(address컬럼)> <출력csv>
- 100개/배치, 무료 5req/s, 이어받기 지원
- reputation: 0=중립/미표시, 1=경계, 2=악성(Phish/Hack·Exploit 등)
"""
import csv, json, os, sys, time, urllib.request, urllib.parse

SRC, DST = sys.argv[1], sys.argv[2]
KEY = os.environ.get("ETHERSCAN_KEY") or (sys.argv[3] if len(sys.argv) > 3 else "")
if not KEY:
    sys.exit("ETHERSCAN_KEY 필요")
BATCH = 100

def fetch(addrs):
    url = ("https://api.etherscan.io/v2/api?chainid=1&module=nametag&action=getaddresstag"
           f"&address={','.join(addrs)}&apikey={KEY}")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                d = json.loads(r.read().decode())
            if str(d.get("status")) == "1" and isinstance(d.get("result"), list):
                return d["result"]
            # rate limit / NOTOK
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None

done = set()
if os.path.exists(DST):
    with open(DST, encoding="utf-8") as f:
        done = {r["address"].lower() for r in csv.DictReader(f)}
targets = []
seen = set()
with open(SRC, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        a = (r.get("address") or "").strip().lower()
        if a.startswith("0x") and len(a) == 42 and a not in done and a not in seen:
            seen.add(a); targets.append(a)
print(f"검증 대상 {len(targets)} (완료 {len(done)})")

mode = "a" if done else "w"
out = open(DST, mode, newline="", encoding="utf-8")
w = csv.writer(out)
if not done:
    w.writerow(["address", "reputation", "labels", "nametag"])

from collections import Counter
rep = Counter()
for i in range(0, len(targets), BATCH):
    batch = targets[i:i + BATCH]
    res = fetch(batch)
    if res is None:
        print(f"  배치 {i} 실패 — 스킵")
        continue
    got = {x["address"].lower(): x for x in res}
    for a in batch:
        x = got.get(a)
        if x:
            r = x.get("reputation", "")
            rep[r] += 1
            w.writerow([a, r, "|".join(x.get("labels") or []), x.get("nametag") or ""])
        else:
            w.writerow([a, "", "", ""])
    out.flush()
    if (i // BATCH) % 10 == 0:
        print(f"  {i+len(batch)}/{len(targets)}  reputation={dict(rep)}")
    time.sleep(0.25)   # 5 req/s 이내
out.close()
print(f"완료: reputation 분포 {dict(rep)}")
