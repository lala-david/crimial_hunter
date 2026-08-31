# -*- coding: utf-8 -*-
"""Chainabuse 신규 신고만 증분 수집 (front-fill).
사용법: python refresh_chainabuse.py SOL   (또는 ETH)
목록이 최신순이므로 앞에서부터 읽어 이미 아는 report id를 연속으로 만나면 중단.
crawl_chainabuse.py의 오프셋 이어받기는 최초 전량 수집용 — 갱신에는 이 스크립트 사용.
"""
import json, os, sys, time, urllib.request

CHAIN = (sys.argv[1] if len(sys.argv) > 1 else "SOL").upper()
PAGE = 50
MAX_PAGES = 400          # 안전 상한 (한 번에 최대 2만 신고)
STOP_AFTER_KNOWN = 3     # 새 신고 0건인 페이지가 연속 N번이면 종료

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out_path = os.path.join(BASE, "raw", f"chainabuse_reports_{CHAIN}.jsonl")

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

known = set()
if os.path.exists(out_path):
    with open(out_path, encoding="utf-8") as f:
        for line in f:
            try:
                known.add(json.loads(line)["id"])
            except Exception:
                pass
print(f"[{CHAIN}] 기존 신고 {len(known)}건 — 신규분 탐색 시작")

after = None
new_cnt = 0
known_streak = 0
with open(out_path, "a", encoding="utf-8") as f:
    for page in range(MAX_PAGES):
        data = fetch(after)
        rep = data.get("data", {}).get("reports")
        if not rep:
            print("응답 이상:", json.dumps(data)[:300])
            break
        fresh = [e["node"] for e in rep["edges"] if e["node"]["id"] not in known]
        for n in fresh:
            f.write(json.dumps(n, ensure_ascii=False) + "\n")
            known.add(n["id"])
        new_cnt += len(fresh)
        known_streak = known_streak + 1 if not fresh else 0
        pi = rep["pageInfo"]
        print(f"  p{page+1}: 신규 {len(fresh)} (누적 {new_cnt}, total={rep['totalCount']})")
        if known_streak >= STOP_AFTER_KNOWN or not pi["hasNextPage"]:
            break
        after = pi["endCursor"]
        time.sleep(0.4)

print(f"[{CHAIN}] 완료: 신규 {new_cnt}건 추가 -> {out_path}")
