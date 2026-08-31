# -*- coding: utf-8 -*-
"""rugcheck_creators.csv(mint,creator,rugged,score) → rugcheck_creator_sol.csv 집계.
규칙: rugged=True 토큰의 creator만, 공용 배포 인프라(러그토큰 50개 이상 creator) 제외.
"""
import csv, os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "processed")
INFRA_THRESHOLD = 50

cnt = Counter()
with open(os.path.join(OUT, "rugcheck_creators.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        c = (r.get("creator") or "").strip()
        if c and str(r.get("rugged")).lower() == "true":
            cnt[c] += 1

infra = {c for c, n in cnt.items() if n >= INFRA_THRESHOLD}
rows = [[c, "SOL", "rugpull_dev_creator", "rugcheck_creator", f"{n}_rug_tokens",
         "via RugCheck (개인 배포자)", ""]
        for c, n in sorted(cnt.items()) if c not in infra]

with open(os.path.join(OUT, "rugcheck_creator_sol.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(rows)
print(f"-> rugcheck_creator_sol.csv: {len(rows)} creators "
      f"(인프라 제외 {len(infra)}개: {[(c[:8], n) for c, n in cnt.most_common(5) if c in infra]})")
