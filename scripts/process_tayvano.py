# -*- coding: utf-8 -*-
"""tayvano lazarus-bluenoroff-research → 두 파일로 분리 추출.
- tayvano_lazarus.csv: hacks-and-thefts/, more-hacks-and-thefts/ (ETH+SOL)
- tayvano_trace_extra.csv: dprk-it-workers/, malicious-shit/, nick-franklin/ (ETH만)
  IT worker 급여지갑 등 무고한 상대방 혼입 가능 → TAINTED_TRACE로 등급화에서 격리:
  Etherscan rep 2/3 독립 확정만 confirmed 진입. SOL은 검증수단이 없어 wallet 마스터 미편입.
"""
import csv, os, re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "raw", "tayvano_x", "lazarus-bluenoroff-research-main")
OUT = os.path.join(BASE, "sources")

KEEP_DIRS = ["hacks-and-thefts", "more-hacks-and-thefts"]
EXTRA_DIRS = ["dprk-it-workers", "malicious-shit", "nick-franklin"]
EXTS = {".md", ".csv", ".txt", ".json"}

ETH_RE = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
SOL_RE = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])")

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
IDX = {c: i for i, c in enumerate(ALPH)}

def valid_sol(s):
    n = 0
    for c in s:
        if c not in IDX:
            return False
        n = n * 58 + IDX[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return len(b"\x00" * (len(s) - len(s.lstrip("1"))) + body) == 32

def scan(dirs):
    found = {}   # (chain, addr) -> (top_dir, first_file)
    files = 0
    for top in dirs:
        for dirpath, _, names in os.walk(os.path.join(ROOT, top)):
            for name in names:
                if os.path.splitext(name)[1].lower() not in EXTS:
                    continue
                files += 1
                try:
                    text = open(os.path.join(dirpath, name), encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for m in ETH_RE.findall(text):
                    found.setdefault(("ETH", m.lower()), (top, name))
                for m in SOL_RE.findall(text):
                    if valid_sol(m):
                        found.setdefault(("SOL", m), (top, name))
    return found, files

def dump(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writerows(rows)
    print(f"-> {name}: {len(rows)} rows  체인 {dict(Counter(r[1] for r in rows))}  "
          f"디렉토리 {dict(Counter(r[4] for r in rows))}")

laz, n1 = scan(KEEP_DIRS)
dump("tayvano_lazarus.csv",
     [[a, ch, "state_actor_dprk", "tayvano_lazarus", top, fn[:60], ""]
      for (ch, a), (top, fn) in sorted(laz.items())])

extra, n2 = scan(EXTRA_DIRS)
# Lazarus 분과 겹치면 Lazarus 쪽 우선, ETH만 (SOL은 검증 불가 → 미편입)
dump("tayvano_trace_extra.csv",
     [[a, ch, "dprk_trace", "tayvano_trace_extra", top, fn[:60], ""]
      for (ch, a), (top, fn) in sorted(extra.items())
      if ch == "ETH" and (ch, a) not in laz])
print(f"(파싱 파일: lazarus {n1} / extra {n2})")
