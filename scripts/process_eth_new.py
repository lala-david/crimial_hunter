# -*- coding: utf-8 -*-
"""이더리움 신규 외부 소스 정규화 (리서치 발굴, 전부 실근거):
① Chainalysis Sanctions Oracle 미러 (0xsequence) — 제재
② RevokeCash approval-exploit-list — 익스플로잇/악성 spender 컨트랙트 (큐레이션)
③ 폰지 3종: Blockchain@Unica, PlusToken(Elementus) — 수사/큐레이션 ground-truth
출력: sources/chainalysis_oracle_eth.csv, revokecash_eth.csv, ponzi_eth.csv
"""
import csv, json, os, re, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "sources")
ETH = re.compile(r"^0x[0-9a-fA-F]{40}$")

def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def save(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
        w.writerows(rows)
    print(f"-> {name}: {len(rows)}개")

# ① Chainalysis Sanctions Oracle
try:
    d = json.loads(get("https://raw.githubusercontent.com/0xsequence/chainalysis/master/index/sanctioned_addresses.json"))
    addrs = set()
    def walk(x):
        if isinstance(x, str) and ETH.match(x):
            addrs.add(x.lower())
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    save("chainalysis_oracle_eth.csv",
         [[a, "ETH", "sanctions", "chainalysis_oracle", "sanctioned", "Chainalysis 온체인 제재 오라클", ""]
          for a in sorted(addrs)])
except Exception as e:
    print(f"  (Chainalysis 실패: {e})")

# ② RevokeCash approval-exploit-list
try:
    tree = json.loads(get("https://api.github.com/repos/RevokeCash/approval-exploit-list/git/trees/main?recursive=1"))
    files = [t["path"] for t in tree.get("tree", [])
             if t["path"].startswith("exploits/") and t["path"].endswith(".json")]
    rows, seen = [], set()
    for path in files:
        try:
            d = json.loads(get("https://raw.githubusercontent.com/RevokeCash/approval-exploit-list/main/" + path))
        except Exception:
            continue
        name = (d.get("name") or path.split("/")[-1].replace(".json", ""))[:40]
        date = (d.get("date") or "")[:10]
        for e in (d.get("addresses") or []):
            a = (e.get("address") or "").strip().lower()
            if ETH.match(a) and a not in seen:
                seen.add(a)
                rows.append([a, "ETH", "exploit", "revokecash", "malicious spender/exploit", name, date])
    save("revokecash_eth.csv", rows)
    print(f"   ({len(files)}개 사건 파일)")
except Exception as e:
    print(f"  (RevokeCash 실패: {e})")

# ③ 폰지 큐레이션
ponzi, seen = [], set()
for url, lab in [
    ("https://raw.githubusercontent.com/blockchain-unica/ethereum-ponzi/master/ponzi-addresses.csv", "unica"),
    ("https://raw.githubusercontent.com/elementus-io/plustoken/master/plustoken-ethereum-addresses.csv", "plustoken"),
]:
    try:
        text = get(url)
    except Exception as e:
        print(f"  (폰지 {lab} 실패: {e})")
        continue
    for a in re.findall(r"0x[0-9a-fA-F]{40}", text):
        a = a.lower()
        if a not in seen:
            seen.add(a)
            src = "ponzi_unica" if lab == "unica" else "elementus_plustoken"
            ponzi.append([a, "ETH", "ponzi", src, lab, "수사/큐레이션 ground-truth", ""])
save("ponzi_eth.csv", ponzi)
