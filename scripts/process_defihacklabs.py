# -*- coding: utf-8 -*-
"""DeFiHackLabs(사건 재현 PoC 저장소)에서 '공격자' 주소만 추출.
attacker/exploiter/hacker 키워드가 있는 줄의 0x 주소만 채택 — 피해 컨트랙트·라우터·토큰 배제.
파일명 = 사건명 (예: 2024-07/MonoSwap_exp.sol → MonoSwap).
출력: sources/defihacklabs_eth.csv
"""
import csv, os, re, subprocess, urllib.request
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
ROOT = os.path.join(RAW, "DeFiHackLabs-main")
OUT = os.path.join(BASE, "sources")

# 최신 tarball 재다운로드 (실패 시 기존 추출본 사용)
try:
    tgz = os.path.join(RAW, "defihacklabs.tar.gz")
    req = urllib.request.Request(
        "https://github.com/SunWeb3Sec/DeFiHackLabs/archive/refs/heads/main.tar.gz",
        headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tgz + ".tmp", "wb") as f:
        f.write(r.read())
    if os.path.getsize(tgz + ".tmp") > 500_000:
        os.replace(tgz + ".tmp", tgz)
        subprocess.run(["tar", "-xzf", tgz, "-C", RAW], check=True, timeout=300)
        print("  defihacklabs 최신 반영")
except Exception as e:
    print(f"  (defihacklabs 갱신 실패, 기존 사용: {e})")

ADDR = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
KEY = re.compile(r"attack|exploit|hacker|malicious|drainer|scammer", re.I)
# 오탐 방지: 같은 줄에 피해자/컨트랙트 단서만 있으면 제외
NEG = re.compile(r"victim|vulnerable|proxy admin|router|factory|pair|pool address", re.I)

found = {}   # addr -> (incident, date)
stats = Counter()
for dirpath, _, names in os.walk(os.path.join(ROOT, "src")):
    for name in names:
        if not name.endswith(".sol"):
            continue
        incident = re.sub(r"_exp.*$|\.sol$", "", name)
        m = re.search(r"(\d{4})[-/](\d{2})", dirpath.replace("\\", "/"))
        day = f"{m.group(1)}-{m.group(2)}" if m else ""
        try:
            text = open(os.path.join(dirpath, name), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for line in text.splitlines():
            if not KEY.search(line) or NEG.search(line):
                continue
            for a in ADDR.findall(line):
                a = a.lower()
                if a not in found:
                    found[a] = (incident, day)
                    stats["addr"] += 1

rows = [[a, "ETH", "defi_hack_attacker", "defihacklabs", inc[:40], "PoC 사건 재현 repo", day]
        for a, (inc, day) in sorted(found.items())]
with open(os.path.join(OUT, "defihacklabs_eth.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(rows)
years = Counter(day[:4] for _, (_, day) in found.items() if day)
print(f"-> defihacklabs_eth.csv: {len(rows)}개 (연도별 {dict(sorted(years.items()))})")
