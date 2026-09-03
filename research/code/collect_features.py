# -*- coding: utf-8 -*-
"""러그풀 조기감지 특징 수집 — 스캠 토큰 mint의 RugCheck report에서 온체인 지표 추출.
사용법: python collect_features.py <mint목록.txt> <출력.csv> [최대건수]
- 이어받기(락파일), invalid mint(=이미 rug 완료로 계정 닫힘) 기록
- 특징: 권한 생존 / 홀더 집중 / 유동성 / creator 재범 / 위험태그 / 발행플랫폼
"""
import csv, json, os, sys, time, urllib.request, urllib.error

SRC, DST = sys.argv[1], sys.argv[2]
CAP = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
LOCK = DST + ".lock"

if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 900:
    sys.exit("다른 인스턴스 실행 중")
open(LOCK, "w").write(str(os.getpid()))

def fetch(mint):
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode()), None
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None, "invalid_or_closed"   # 이미 rug 완료·무효
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None, "fetch_failed"

FIELDS = ["mint", "status", "mint_auth_live", "freeze_auth_live", "top1_pct", "top10_pct",
          "total_holders", "lp_providers", "liquidity_usd", "creator_tokens",
          "insiders_detected", "launchpad", "rugged", "score", "risks"]

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
        if len(targets) >= CAP:
            break
print(f"수집 대상 {len(targets)} (완료 {len(done)})", flush=True)

mode = "a" if done else "w"
out = open(DST, mode, newline="", encoding="utf-8")
w = csv.DictWriter(out, fieldnames=FIELDS)
if not done:
    w.writeheader()

from collections import Counter
stat = Counter()
try:
    for i, mint in enumerate(targets):
        d, err = fetch(mint)
        if d is None:
            w.writerow({"mint": mint, "status": err or "none"})
            stat[err or "none"] += 1
        else:
            top = d.get("topHolders") or []
            top1 = top[0].get("pct") if top else None
            top10 = sum(h.get("pct") or 0 for h in top[:10]) if top else None
            creator = d.get("creator")
            ctokens = d.get("creatorTokens")
            row = {
                "mint": mint, "status": "ok",
                "mint_auth_live": 1 if d.get("mintAuthority") else 0,
                "freeze_auth_live": 1 if d.get("freezeAuthority") else 0,
                "top1_pct": round(top1, 4) if isinstance(top1, (int, float)) else "",
                "top10_pct": round(top10, 4) if isinstance(top10, (int, float)) else "",
                "total_holders": d.get("totalHolders") or "",
                "lp_providers": d.get("totalLPProviders") or 0,
                "liquidity_usd": round(d.get("totalMarketLiquidity") or 0, 2),
                "creator_tokens": len(ctokens) if isinstance(ctokens, list) else "",
                "insiders_detected": 1 if d.get("graphInsidersDetected") else 0,
                "launchpad": str(d.get("launchpad") or d.get("deployPlatform") or "")[:20],
                "rugged": 1 if d.get("rugged") else 0,
                "score": d.get("score") or "",
                "risks": "|".join((r.get("name") or "")[:30] for r in (d.get("risks") or []))[:200],
            }
            w.writerow(row)
            stat["ok"] += 1
        if (i + 1) % 50 == 0:
            out.flush()
            open(LOCK, "w").write(str(os.getpid()))
            print(f"  {i+1}/{len(targets)}  {dict(stat)}", flush=True)
        time.sleep(0.35)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: {dict(stat)}")
