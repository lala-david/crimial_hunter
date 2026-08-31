# -*- coding: utf-8 -*-
"""RugCheck로 스캠 토큰 mint의 creator(스캐머 dev 지갑)를 역추출.
사용법: python resolve_creators.py <mint목록> <출력csv>
- 무료 RugCheck API, 이어받기 지원, 레이트리밋 대비 지연/재시도
"""
import csv, json, os, sys, time, urllib.request

SRC, DST = sys.argv[1], sys.argv[2]

def fetch(mint):
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None

done = set()
if os.path.exists(DST):
    with open(DST, encoding="utf-8") as f:
        done = {r["mint"] for r in csv.DictReader(f)}
targets = []
with open(SRC, encoding="utf-8") as f:
    for line in f:
        m = line.strip()
        if m and m not in done:
            targets.append(m)
print(f"creator 역추출 대상 {len(targets)} (완료 {len(done)})")

mode = "a" if done else "w"
out = open(DST, mode, newline="", encoding="utf-8")
w = csv.writer(out)
if not done:
    w.writerow(["mint", "creator", "rugged", "score"])

ok = 0
for i, mint in enumerate(targets):
    d = fetch(mint)
    if d is None:
        w.writerow([mint, "", "", ""])
    else:
        w.writerow([mint, d.get("creator") or "", d.get("rugged"), d.get("score")])
        if d.get("creator"):
            ok += 1
    if (i + 1) % 50 == 0:
        out.flush()
        print(f"  {i+1}/{len(targets)}  creator확보 {ok}")
    time.sleep(1.1)
out.close()
print(f"완료: creator {ok}개 확보")
