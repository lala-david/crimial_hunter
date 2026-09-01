# -*- coding: utf-8 -*-
"""rekt.news 크롤링 — leaderboard의 전체 사건 글에서 주소 추출.
robots.txt: /api만 Disallow, 콘텐츠 허용. 예의상 지연·UA 명시.
- 1단계: leaderboard에서 사건 URL 전량 수집
- 2단계: 각 글 본문 HTML 저장(raw/rekt/) + 주소 추출
- 주소는 '무조건 악성 아님' — 사건 문맥(제목·주변텍스트)과 함께 저장해 사후 검수 가능하게.
출력: raw/rekt/*.html, raw/rekt_extracted.jsonl
"""
import json, os, re, time, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
HTMLDIR = os.path.join(RAW, "rekt")
os.makedirs(HTMLDIR, exist_ok=True)
OUT = os.path.join(RAW, "rekt_extracted.jsonl")

UA = "Mozilla/5.0 (compatible; research-crawler; +github.com/lala-david/crimial_hunter)"
ETH = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
SOL = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])")
TAG = re.compile(r"<[^>]+>")

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
IDX = {c: i for i, c in enumerate(ALPH)}
def valid_sol(s):
    if not (32 <= len(s) <= 44):
        return False
    n = 0
    for c in s:
        if c not in IDX:
            return False
        n = n * 58 + IDX[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return len(b"\x00" * (len(s) - len(s.lstrip("1"))) + body) == 32

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")

# 1) leaderboard에서 사건 URL 전량
lb = get("https://rekt.news/leaderboard")
slugs = sorted(set(re.findall(r'href="(/[a-z0-9][a-z0-9\-]+)"', lb)))
skip = {"/leaderboard", "/research", "/total-exposure", "/api"}
slugs = [s for s in slugs if s not in skip and not s.startswith(("/tag", "/author", "/page"))]
print(f"사건 후보 URL: {len(slugs)}")

done = set()
if os.path.exists(OUT):
    with open(OUT, encoding="utf-8") as f:
        for line in f:
            try:
                done.add(json.loads(line)["slug"])
            except Exception:
                pass

out = open(OUT, "a", encoding="utf-8")
SOL_KEYWORDS = re.compile(r"solana|\bSOL\b|phantom|raydium|serum|magic eden|pump\.fun|jupiter|saber|mango", re.I)
n_new = 0
for i, slug in enumerate(slugs):
    if slug in done:
        continue
    try:
        html = get("https://rekt.news" + slug)
    except Exception as e:
        print(f"  {slug} 실패: {e}")
        continue
    # 본문 저장
    with open(os.path.join(HTMLDIR, slug.strip("/") + ".html"), "w", encoding="utf-8") as f:
        f.write(html)
    text = TAG.sub(" ", html)
    # 제목
    mt = re.search(r"<title>(.*?)</title>", html, re.S)
    title = (mt.group(1).strip() if mt else slug)[:120]
    eth_addrs = sorted(set(a.lower() for a in ETH.findall(text)))
    sol_addrs = sorted(set(a for a in SOL.findall(text) if valid_sol(a)))
    is_sol_related = bool(SOL_KEYWORDS.search(text))
    rec = {"slug": slug, "title": title, "sol_related": is_sol_related,
           "eth_count": len(eth_addrs), "sol_count": len(sol_addrs),
           "eth": eth_addrs, "sol": sol_addrs}
    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out.flush()
    n_new += 1
    if is_sol_related and sol_addrs:
        print(f"  [SOL] {slug}: SOL {len(sol_addrs)}개  ({title[:50]})")
    if (i + 1) % 25 == 0:
        print(f"  진행 {i+1}/{len(slugs)}  신규 {n_new}")
    time.sleep(0.6)   # 예의상 지연
out.close()
print(f"완료: 신규 {n_new}건 크롤. -> {OUT}")
