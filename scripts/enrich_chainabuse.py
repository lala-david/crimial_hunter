# -*- coding: utf-8 -*-
"""Chainabuse API로 신고 주소에 스캠 카테고리를 부여한다.
사용법: CHAINABUSE_API_KEY 환경변수 설정 후
  python enrich_chainabuse.py <입력CSV> <출력CSV> [쿼터하한]
- 입력 CSV: 1열이 address (process.py 산출물)
- 월 750회 레이트리밋이므로 ratelimit-remaining이 하한 아래로 내려가면 중단(재실행 시 이어받기)
"""
import base64, csv, json, os, sys, time, urllib.request

KEY = os.environ.get("CHAINABUSE_API_KEY")
if not KEY:
    sys.exit("CHAINABUSE_API_KEY 환경변수가 필요합니다")

src, dst = sys.argv[1], sys.argv[2]
quota_floor = int(sys.argv[3]) if len(sys.argv) > 3 else 500

auth = base64.b64encode(f"{KEY}:{KEY}".encode()).decode()

done = set()
if os.path.exists(dst):
    with open(dst, encoding="utf-8") as f:
        done = {r["address"] for r in csv.DictReader(f)}
    out = open(dst, "a", newline="", encoding="utf-8")
    w = csv.writer(out)
else:
    out = open(dst, "w", newline="", encoding="utf-8")
    w = csv.writer(out)
    w.writerow(["address", "report_count", "categories", "trusted_any", "first_reported", "last_reported"])

with open(src, encoding="utf-8") as f:
    targets = [r["address"] for r in csv.DictReader(f) if r["address"] not in done]

print(f"조회 대상 {len(targets)}개 (기존 완료 {len(done)}개)")
remaining = None
for i, addr in enumerate(targets):
    req = urllib.request.Request(
        f"https://api.chainabuse.com/v0/reports?address={addr}&perPage=50",
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json",
                 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            remaining = resp.headers.get("ratelimit-remaining")
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  {addr}: 오류 {e} — 5초 후 계속")
        time.sleep(5)
        continue
    reports = data.get("reports", [])
    cats = sorted({r.get("scamCategory") or "" for r in reports} - {""})
    dates = sorted(r.get("createdAt", "")[:10] for r in reports if r.get("createdAt"))
    trusted = any(r.get("trusted") for r in reports)
    w.writerow([addr, data.get("count", len(reports)), "|".join(cats), trusted,
                dates[0] if dates else "", dates[-1] if dates else ""])
    if (i + 1) % 20 == 0:
        out.flush()
        print(f"  진행 {i+1}/{len(targets)} (quota 남음: {remaining})")
    if remaining is not None and int(remaining) <= quota_floor:
        print(f"쿼터 하한({quota_floor}) 도달 — 중단. 다음 달 또는 하한 조정 후 재실행하면 이어받습니다.")
        break
    time.sleep(0.35)
out.close()
print(f"완료. quota 남음: {remaining}")
