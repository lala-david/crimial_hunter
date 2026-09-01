# -*- coding: utf-8 -*-
"""rekt 크롤 결과 → 주소별 문맥 판별 → 공격자 주소만 추출.
사용자 지침: 무조건 악성 아님. 주소 주변 텍스트로 attacker/victim/normal 분류.
- ATTACKER 문맥(attacker/exploiter/hacker/drainer address) → 채택
- 정상 문맥(multisig member/security council/legitimate/victim/treasury/deployer/proposal) → 제외
- 애매 → review 파일(수동 검수용), 마스터 미편입
출력: sources/rekt_attacker.csv (ETH/SOL), raw/rekt_review.jsonl (애매)
"""
import csv, json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
HTMLDIR = os.path.join(RAW, "rekt")
OUT = os.path.join(BASE, "sources")
TAG = re.compile(r"<[^>]+>")

ETH = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
SOL = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])")

# 양성/음성 문맥 (주소 앞뒤 윈도우에서 검색)
POS = re.compile(r"attacker|exploiter|hacker|drainer|malicious|thief|stole|scammer|"
                 r"attack address|exploit contract|funds (?:to|were sent)", re.I)
NEG = re.compile(r"multisig member|security council|legitimate|victim|treasury|vault|"
                 r"deployer|team wallet|proposal|governance|realms\.today|"
                 r"official|recovery|whitehat|white hat|refund|"
                 r"hot wallet|deposit address|cold wallet|mint address|token on|"
                 r"dex screener|dexscreener|cvt|phemex hot|exchange wallet", re.I)
WINDOW = 100

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
IDX = {c: i for i, c in enumerate(ALPH)}
HEXONLY = re.compile(r"^[0-9a-f]+$")   # ETH 주소/tx 조각이 우연히 base58 통과하는 것 배제
def valid_sol(s):
    if not (32 <= len(s) <= 44):
        return False
    if HEXONLY.match(s):               # 소문자 hex-only → 솔라나 pubkey 아님
        return False
    if s.startswith("addr"):           # Cardano bech32
        return False
    if s.startswith("T") and len(s) == 34:   # TRON base58check
        return False
    n = 0
    for c in s:
        if c not in IDX:
            return False
        n = n * 58 + IDX[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return len(b"\x00" * (len(s) - len(s.lstrip("1"))) + body) == 32

rows = [json.loads(l) for l in open(os.path.join(RAW, "rekt_extracted.jsonl"), encoding="utf-8")]
attacker = []      # [addr, chain, ...]
review = []
from collections import Counter
stat = Counter()

for r in rows:
    slug = r["slug"]
    hp = os.path.join(HTMLDIR, slug.strip("/") + ".html")
    if not os.path.exists(hp):
        continue
    text = re.sub(r"\s+", " ", TAG.sub(" ", open(hp, encoding="utf-8").read()))
    title = r["title"]
    for chain, addrs in (("ETH", r["eth"]), ("SOL", r["sol"])):
        for a in addrs:
            if chain == "SOL" and not valid_sol(a):
                continue
            # 모든 등장 위치의 문맥 합침
            ctxs = []
            start = 0
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
                                 "exploit", "rekt_news", slug.strip("/")[:40],
                                 snippet, ""])
                stat[f"{chain}_attacker"] += 1
            elif neg and not pos:
                stat[f"{chain}_excluded_normal"] += 1
            else:
                review.append({"addr": a, "chain": chain, "slug": slug,
                               "pos": pos, "neg": neg, "title": title, "snippet": snippet})
                stat[f"{chain}_review"] += 1

# 중복 제거 (주소 단위, 첫 문맥 유지)
seen = set()
uniq = []
for row in attacker:
    k = (row[1], row[0])
    if k in seen:
        continue
    seen.add(k)
    uniq.append(row)

with open(os.path.join(OUT, "rekt_attacker.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(uniq)
with open(os.path.join(RAW, "rekt_review.jsonl"), "w", encoding="utf-8") as f:
    for x in review:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")

print(f"-> rekt_attacker.csv: {len(uniq)}개 (ETH {sum(1 for r in uniq if r[1]=='ETH')} / SOL {sum(1 for r in uniq if r[1]=='SOL')})")
print(f"   분류: {dict(stat)}")
print(f"   review(수동검수 대기): {len(review)} -> raw/rekt_review.jsonl")
