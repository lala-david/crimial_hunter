# -*- coding: utf-8 -*-
"""De.Fi Rekt 사건 description에서 공격자 주소 추출 (문맥 판별).
process_rekt.py와 동일 철학: attacker 문맥만 채택, 피해자/멀티시그/핫월렛/mint/타체인/hex 배제.
De.Fi는 chaindIds 필드로 체인 명시 → 솔라나(12)/이더(1) 사건 구분에 활용.
출력: sources/defi_rekt_attacker.csv, raw/defi_rekt_review.jsonl
"""
import csv, json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "sources")
TAG = re.compile(r"<[^>]+>")

ETH = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
SOL = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])")
HEXONLY = re.compile(r"^[0-9a-f]+$")

POS = re.compile(r"attacker|exploiter|hacker|drainer|malicious|thief|stole|scammer|"
                 r"attack address|exploit contract|drained|drainer address", re.I)
NEG = re.compile(r"multisig member|security council|legitimate|victim|treasury|vault|"
                 r"deployer|team wallet|proposal|governance|realms\.today|"
                 r"official|recovery|whitehat|white hat|refund|"
                 r"hot wallet|deposit address|cold wallet|mint address|token on|"
                 r"dex screener|dexscreener|exchange wallet|liquidity at|"
                 r"program address|program\)|protocol address|contract address|"
                 r"the .{0,20}program|pool address", re.I)
WINDOW = 110

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
IDX = {c: i for i, c in enumerate(ALPH)}
def valid_sol(s):
    if not (32 <= len(s) <= 44) or HEXONLY.match(s):
        return False
    if s.startswith("addr") or (s.startswith("T") and len(s) == 34):
        return False
    n = 0
    for c in s:
        if c not in IDX:
            return False
        n = n * 58 + IDX[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return len(b"\x00" * (len(s) - len(s.lstrip("1"))) + body) == 32

rows = [json.loads(l) for l in open(os.path.join(RAW, "defi_rekt.jsonl"), encoding="utf-8")]
SOL_ID = 24   # De.Fi rekts의 chaindIds에서 솔라나 = 24 (chains 엔드포인트의 12와 불일치)
attacker, review = [], []
from collections import Counter
stat = Counter()

for r in rows:
    desc = r.get("description") or ""
    if not desc:
        continue
    text = re.sub(r"\s+", " ", TAG.sub(" ", desc))
    proj = (r.get("projectName") or "")[:40]
    chains = r.get("chaindIds") or []
    sol_event = SOL_ID in chains
    for chain, addrs in (("ETH", set(a.lower() for a in ETH.findall(text))),
                         ("SOL", set(a for a in SOL.findall(text) if valid_sol(a)))):
        # 솔라나 주소는 솔라나 사건에서만 신뢰 (타 체인 사건의 base58은 노이즈 위험)
        if chain == "SOL" and not sol_event:
            continue
        for a in addrs:
            ctxs, start = [], 0
            while True:
                i = text.find(a, start)
                if i < 0:
                    break
                ctxs.append(text[max(0, i - WINDOW):i + len(a) + WINDOW])
                start = i + len(a)
            ctx = " ".join(ctxs)
            pos, neg = bool(POS.search(ctx)), bool(NEG.search(ctx))
            snippet = (ctxs[0].replace(a, "@")[:180] if ctxs else "")
            if pos and not neg:
                attacker.append([a.lower() if chain == "ETH" else a, chain,
                                 "exploit", "defi_rekt", proj, snippet, (r.get("date") or "")[:10]])
                stat[f"{chain}_attacker"] += 1
            elif neg and not pos:
                stat[f"{chain}_excluded"] += 1
            else:
                review.append({"addr": a, "chain": chain, "project": proj,
                               "pos": pos, "neg": neg, "snippet": snippet})
                stat[f"{chain}_review"] += 1

seen, uniq = set(), []
for row in attacker:
    k = (row[1], row[0])
    if k not in seen:
        seen.add(k); uniq.append(row)

with open(os.path.join(OUT, "defi_rekt_attacker.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(uniq)
with open(os.path.join(RAW, "defi_rekt_review.jsonl"), "w", encoding="utf-8") as f:
    for x in review:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")

print(f"-> defi_rekt_attacker.csv: {len(uniq)}개 "
      f"(ETH {sum(1 for r in uniq if r[1]=='ETH')} / SOL {sum(1 for r in uniq if r[1]=='SOL')})")
print(f"   분류: {dict(stat)} | review {len(review)}")
