# -*- coding: utf-8 -*-
"""ChainPatrol asset/list에서 BLOCKED 주소를 전량 크롤링(커서 페이징).
CAIP-10(content) 파싱: 'solana:<genesis>:<addr>' / 'eip155:1:<0x..>'
출력: raw/chainpatrol_blocked.jsonl (SOL/ETH만)
"""
import json, os, time, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
URL = "https://app.chainpatrol.io/api/v2/asset/list"
PAGE = 5000
HEADERS = {"Content-Type": "application/json",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}

def caip_parse(content):
    parts = content.split(":")
    ns = parts[0]
    addr = parts[-1]
    if ns == "solana":
        return "SOL", addr
    if ns == "eip155":
        return "ETH", addr
    return ns.upper(), addr

def fetch(next_page):
    body = {"type": "ADDRESS", "status": "BLOCKED", "per_page": PAGE}
    if next_page:
        body["next_page"] = next_page
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=HEADERS, method="POST")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print(f"  재시도 {attempt+1} ({e})")
            time.sleep(3 * (attempt + 1))
    raise SystemExit("ChainPatrol 반복 실패")

out = os.path.join(RAW, "chainpatrol_blocked.jsonl")
next_page = None
total = 0
from collections import Counter
dist = Counter()
with open(out, "w", encoding="utf-8") as f:
    while True:
        data = fetch(next_page)
        assets = data.get("assets", [])
        if not assets:
            break
        for a in assets:
            chain, addr = caip_parse(a.get("content", ""))
            dist[chain] += 1
            if chain in ("SOL", "ETH"):
                rec = {"address": addr, "chain": chain,
                       "blockedAt": a.get("blockedAt"), "updatedAt": a.get("updatedAt")}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        total += len(assets)
        next_page = data.get("next_page")
        print(f"  누적 {total} (SOL={dist['SOL']}, ETH={dist['ETH']})  next={next_page}")
        if not next_page:
            break
        time.sleep(0.3)

print(f"[ChainPatrol] 총 {total} assets, 체인분포 {dict(dist)} -> {out}")
