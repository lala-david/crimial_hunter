# -*- coding: utf-8 -*-
"""러그풀 메커니즘 유형 분류용 온체인 특징 수집 (RugCheck report 전체 필드).
사용법: python collect_mechanism.py <mint목록.txt> <출력.csv> [최대건수]
유동성걷어가기 / 개발자덤프 / 허니팟 / 무한발행 / 인사이더 를 판별할 필드를 뽑는다.
"""
import csv, json, os, sys, time, urllib.request, urllib.error

SRC, DST = sys.argv[1], sys.argv[2]
CAP = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
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
                return None, "closed"
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None, "fail"

FIELDS = ["mint", "status",
          "mint_auth", "freeze_auth",              # 무한발행/허니팟 권한
          "top1_pct", "top10_pct", "holders",      # 집중도
          "lp_providers", "lp_locked_pct", "liquidity_usd",  # 유동성 걷어가기
          "transfer_fee_pct",                      # 허니팟 세금
          "creator_rug_count",                     # creator 재범
          "insiders", "insider_pct",               # 인사이더/번들
          "launchpad", "rugged", "score",
          "top_risk"]                              # 최상위 위험 태그

done = set()
if os.path.exists(DST):
    for r in csv.DictReader(open(DST, encoding="utf-8")):
        done.add(r["mint"])
targets = []
for line in open(SRC, encoding="utf-8"):
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
            w.writerow({"mint": mint, "status": err})
            stat[err] += 1
        else:
            top = d.get("topHolders") or []
            # LP 잠금 비율: markets의 lp lockedPct 최대
            lp_locked = 0.0
            for mk in (d.get("markets") or []):
                lp = mk.get("lp") or {}
                lp_locked = max(lp_locked, lp.get("lpLockedPct") or 0)
            # 인사이더
            insiders = d.get("graphInsidersDetected") or 0
            ins_pct = 0.0
            for net in (d.get("insiderNetworks") or []):
                ins_pct = max(ins_pct, net.get("tokenAmount") or 0)
            risks = d.get("risks") or []
            row = {
                "mint": mint, "status": "ok",
                "mint_auth": 1 if d.get("mintAuthority") else 0,
                "freeze_auth": 1 if d.get("freezeAuthority") else 0,
                "top1_pct": round(top[0].get("pct"), 3) if top and isinstance(top[0].get("pct"), (int, float)) else "",
                "top10_pct": round(sum(h.get("pct") or 0 for h in top[:10]), 2) if top else "",
                "holders": d.get("totalHolders") or "",
                "lp_providers": d.get("totalLPProviders") or 0,
                "lp_locked_pct": round(lp_locked, 2),
                "liquidity_usd": round(d.get("totalMarketLiquidity") or 0, 2),
                "transfer_fee_pct": (d.get("transferFee") or {}).get("pct") or 0,
                "creator_rug_count": len(d.get("creatorTokens") or []) if isinstance(d.get("creatorTokens"), list) else "",
                "insiders": 1 if insiders else 0,
                "insider_pct": round(ins_pct, 2),
                "launchpad": str(d.get("launchpad") or d.get("deployPlatform") or "")[:20],
                "rugged": 1 if d.get("rugged") else 0,
                "score": d.get("score") or "",
                "top_risk": (risks[0].get("name") if risks else "")[:30] if risks else "",
            }
            w.writerow(row)
            stat["ok"] += 1
        if (i + 1) % 50 == 0:
            out.flush(); open(LOCK, "w").write(str(os.getpid()))
            print(f"  {i+1}/{len(targets)}  {dict(stat)}", flush=True)
        time.sleep(0.35)
finally:
    out.close()
    if os.path.exists(LOCK):
        os.remove(LOCK)
print(f"완료: {dict(stat)}")
