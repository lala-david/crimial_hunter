# -*- coding: utf-8 -*-
"""Chainabuse graphql-proxy로 체인별 신고를 전량 크롤링한다.
사용법: python crawl_chainabuse.py SOL   (또는 ETH)
출력: raw/chainabuse_reports_<chain>.jsonl (report 단위) + processed에서 정규화
"""
import base64, json, os, sys, time, urllib.request

CHAIN = (sys.argv[1] if len(sys.argv) > 1 else "SOL").upper()
PAGE = int(sys.argv[2]) if len(sys.argv) > 2 else 50

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
out_path = os.path.join(RAW, f"chainabuse_reports_{CHAIN}.jsonl")

URL = "https://chainabuse.com/api/graphql-proxy"
QUERY = ("query GetReports($input: ReportsInput, $after: String, $first: Float){"
         "reports(input:$input, after:$after, first:$first){"
         "pageInfo{hasNextPage endCursor} totalCount "
         "edges{node{id createdAt scamCategory categoryDescription checked "
         "biDirectionalVoteCount source description "
         "addresses{address chain domain label}}}}}")
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Origin": "https://www.chainabuse.com",
    "Referer": f"https://www.chainabuse.com/chain/{CHAIN}",
}

def fetch(after):
    body = json.dumps({"query": QUERY,
                       "variables": {"input": {"chains": [CHAIN]}, "first": PAGE, "after": after}}).encode()
    req = urllib.request.Request(URL, data=body, headers=HEADERS, method="POST")
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            wait = min(30, 3 * (attempt + 1))
            print(f"  재시도 {attempt+1} ({e}) — {wait}s")
            time.sleep(wait)
    raise SystemExit("반복 실패")

# 이어받기: 기존 파일 줄 수로 재개 커서 계산 (arrayconnection:<offset>)
after = None
seen = 0
mode = "w"
if os.path.exists(out_path):
    with open(out_path, encoding="utf-8") as f:
        seen = sum(1 for _ in f)
    if seen > 0:
        after = base64.b64encode(f"arrayconnection:{seen-1}".encode()).decode()
        mode = "a"
        print(f"이어받기: {seen}건부터 재개 (after={after})")

total = None
with open(out_path, mode, encoding="utf-8") as f:
    while True:
        data = fetch(after)
        rep = data.get("data", {}).get("reports")
        if not rep:
            print("응답 이상:", json.dumps(data)[:300])
            break
        total = rep["totalCount"]
        for e in rep["edges"]:
            f.write(json.dumps(e["node"], ensure_ascii=False) + "\n")
            seen += 1
        pi = rep["pageInfo"]
        print(f"  {seen}/{total}  (cursor={pi['endCursor']})")
        if not pi["hasNextPage"]:
            break
        after = pi["endCursor"]
        time.sleep(0.4)

print(f"[{CHAIN}] 완료: {seen} reports 저장 -> {out_path}")
