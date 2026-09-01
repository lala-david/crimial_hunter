# -*- coding: utf-8 -*-
"""De.Fi Rekt Database (public-api.de.fi GraphQL) 크롤 → 사건 description 저장.
rekt.news와 동형: description 본문에서 주소 추출은 process_defi_rekt.py가 담당.
- X-Api-Key 인증 (env DEFI_KEY 또는 ~/.defi_key)
- 이어받기: raw/defi_rekt.jsonl (사건 단위 append), 페이지 커서 raw/defi_rekt_page.txt
- De.Fi chain_id: 1=ETH, 2=BNB, 3=Polygon ... 12=Solana (chains 엔드포인트 기준)
"""
import json, os, sys, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(RAW, "defi_rekt.jsonl")
PAGEFILE = os.path.join(RAW, "defi_rekt_page.txt")

KEY = os.environ.get("DEFI_KEY", "")
if not KEY:
    kf = os.path.join(os.path.expanduser("~"), ".defi_key")
    if os.path.exists(kf):
        KEY = open(kf, encoding="ascii").read().strip()
if not KEY:
    sys.exit("DEFI_KEY 필요 (env 또는 ~/.defi_key)")

PAGESIZE = 50
MAXPAGE = int(sys.argv[1]) if len(sys.argv) > 1 else 400

def gql(query):
    data = json.dumps({"query": query}).encode()
    req = urllib.request.Request("https://public-api.de.fi/graphql", data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0", "X-Api-Key": KEY})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode())
            if "errors" in d and not d.get("data"):
                return None, json.dumps(d["errors"])[:200]
            return d.get("data"), None
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            if e.code == 429:
                time.sleep(3 * (attempt + 1)); continue
            return None, f"{e.code}:{body}"
        except Exception as e:
            time.sleep(2 * (attempt + 1))
    return None, "repeated_failure"

done_ids = set()
if os.path.exists(OUT):
    with open(OUT, encoding="utf-8") as f:
        for line in f:
            try:
                done_ids.add(json.loads(line)["id"])
            except Exception:
                pass
start_page = 1
if os.path.exists(PAGEFILE):
    try:
        start_page = int(open(PAGEFILE).read().strip())
    except Exception:
        pass
print(f"기존 {len(done_ids)}건 / {start_page}페이지부터 재개", flush=True)

Q = ("{{ rekts(pageNumber:{p},pageSize:{s}){{ id projectName date fundsLost "
     "fundsReturned chaindIds category issueType description }} }}")

out = open(OUT, "a", encoding="utf-8")
n_new = 0
page = start_page
while page <= MAXPAGE:
    data, err = gql(Q.format(p=page, s=PAGESIZE))
    if err or data is None:
        print(f"  page {page} 중단: {err}")
        break
    items = data.get("rekts") or []
    if not items:
        print(f"  page {page} 빈 결과 — 끝")
        break
    fresh = 0
    for it in items:
        if it["id"] in done_ids:
            continue
        out.write(json.dumps(it, ensure_ascii=False) + "\n")
        done_ids.add(it["id"])
        n_new += 1
        fresh += 1
    out.flush()
    with open(PAGEFILE, "w") as f:
        f.write(str(page + 1))
    if page % 5 == 0:
        print(f"  page {page}: +{fresh} (누적 신규 {n_new}, 총 {len(done_ids)})", flush=True)
    if len(items) < PAGESIZE:
        print(f"  마지막 페이지 도달 (page {page})")
        break
    page += 1
    time.sleep(0.4)
out.close()
print(f"완료: 신규 {n_new}건 (총 {len(done_ids)}) -> {OUT}")
