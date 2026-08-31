# -*- coding: utf-8 -*-
"""GoPlus address_security로 ETH 주소 2차 검증 (무료, 키 불필요).
사용법: python verify_goplus.py <입력csv(address컬럼)> <출력csv> [최대건수]
- 이어받기 지원, 레이트리밋 백오프, 락파일로 동시실행 방지
- 출력: address, flags ("1"인 플래그를 | 로 연결)
"""
import csv, json, os, sys, time, urllib.request

SRC, DST = sys.argv[1], sys.argv[2]
CAP = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.environ.get("GOPLUS_MAX", "4000"))
LOCK = DST + ".lock"

# 동시 실행 방지 (하트비트 10분)
if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 600:
    print("다른 인스턴스 실행 중 — 종료")
    sys.exit(0)
open(LOCK, "w").write(str(os.getpid()))

def fetch(addr):
    url = f"https://api.gopluslabs.io/api/v1/address_security/{addr}?chain_id=1"
    delay = 1.5
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            if d.get("code") == 1:
                return d.get("result") or {}
            time.sleep(delay); delay = min(30, delay * 1.8)   # 레이트리밋 등
        except Exception:
            time.sleep(delay); delay = min(30, delay * 1.8)
    return None

done = set()
if os.path.exists(DST):
    with open(DST, encoding="utf-8") as f:
        done = {r["address"] for r in csv.DictReader(f)}

targets = []
with open(SRC, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        a = (r.get("address") or "").strip().lower()
        if a.startswith("0x") and len(a) == 42 and a not in done:
            targets.append(a)
        if len(targets) >= CAP:
            break
print(f"GoPlus 검증 대상 {len(targets)} (완료 {len(done)}, 상한 {CAP})")

mode = "a" if done else "w"
out = open(DST, mode, newline="", encoding="utf-8")
w = csv.writer(out)
if not done:
    w.writerow(["address", "flags"])

from collections import Counter
dist = Counter()
try:
    for i, a in enumerate(targets):
        res = fetch(a)
        if res is None:
            w.writerow([a, "FETCH_FAILED"])
            continue
        flags = sorted(k for k, v in res.items() if v == "1" and k != "contract_address")
        w.writerow([a, "|".join(flags)])
        for k in flags:
            dist[k] += 1
        if (i + 1) % 200 == 0:
            out.flush()
            open(LOCK, "w").write(str(os.getpid()))   # 하트비트
            print(f"  {i+1}/{len(targets)}  {dict(dist.most_common(5))}", flush=True)
        time.sleep(0.2)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: 플래그 분포 {dict(dist)}")
