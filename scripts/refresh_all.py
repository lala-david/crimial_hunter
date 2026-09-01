# -*- coding: utf-8 -*-
"""전체 리프레시 오케스트레이터 — 스케줄 실행용.
다운로드 → 증분 크롤 → 정규화 → 델타 온체인 분류 → 마스터 재빌드 → (키 있으면) 델타 검증 → 매니페스트.
각 단계는 실패해도 다음 단계로 진행 (이전 산출물 재사용 = 안전).
사용법: python refresh_all.py [--no-crawl]  (크롤 생략하고 재빌드만)
"""
import csv, json, os, re, subprocess, sys, time, urllib.request
from collections import Counter
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
SRC = os.path.join(BASE, "sources")
ETH = os.path.join(BASE, "ethereum")
SOL = os.path.join(BASE, "solana")
ETH_VER = os.path.join(ETH, "verify")
SOL_VER = os.path.join(SOL, "verify")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
NO_CRAWL = "--no-crawl" in sys.argv

failures = []

def step(name, fn):
    print(f"\n===== {name} =====", flush=True)
    t0 = time.time()
    try:
        fn()
        print(f"[OK] {name} ({time.time()-t0:.0f}s)", flush=True)
    except Exception as e:
        failures.append(f"{name}: {e}")
        print(f"[FAIL] {name}: {e}", flush=True)

def run_py(script, *args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    tail = (r.stdout or "").strip().splitlines()[-6:]
    print("\n".join("  " + l for l in tail))
    if r.returncode != 0:
        raise RuntimeError(f"{script} exit {r.returncode}: {(r.stderr or '').strip()[-300:]}")

def download(url, dst, min_bytes=1000, keep_old_if_shrunk=True):
    tmp = dst + ".tmp"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        f.write(r.read())
    new_size = os.path.getsize(tmp)
    if new_size < min_bytes:
        os.remove(tmp)
        raise RuntimeError(f"다운로드 크기 이상 ({new_size}B): {url}")
    if keep_old_if_shrunk and os.path.exists(dst) and new_size < os.path.getsize(dst) * 0.5:
        os.remove(tmp)
        raise RuntimeError(f"기존 대비 50% 미만으로 축소 — 기존 유지: {url}")
    os.replace(tmp, dst)
    print(f"  {os.path.basename(dst)}: {new_size:,}B")

# ---------- 1) 원천 다운로드 ----------
def dl_allenhark():
    download("https://allenhark.com/blacklist.jsonl", os.path.join(RAW, "allenhark_blacklist.jsonl"))

def dl_dawsbot():
    base = "https://raw.githubusercontent.com/dawsbot/eth-labels/v1/data/csv"
    download(f"{base}/accounts.csv", os.path.join(RAW, "ethlabels_accounts.csv"))
    download(f"{base}/tokens.csv", os.path.join(RAW, "ethlabels_tokens.csv"))

# ---------- 2) 증분 크롤 ----------
def crawl():
    run_py("refresh_chainabuse.py", "SOL")
    run_py("refresh_chainabuse.py", "ETH")
    run_py("crawl_chainpatrol.py")

# ---------- 3) 정규화 ----------
def normalize():
    run_py("process_extra.py")
    run_py("process_chainabuse_crawl.py")
    run_py("process_ethlabels_v2.py")
    run_py("process_brianleect.py")          # brianleect Etherscan 라벨 (악성 후보)
    run_py("process_labeled_updates.py")     # ScamSniffer·MEW 라이브 재수집
    run_py("process_tayvano.py")             # tayvano — lazarus/trace_extra 분리
    run_py("process_gov_updates.py")         # OFAC(0xB10C)·Ransomwhere 라이브 갱신
    run_py("process_chainabuse_desc.py")     # 신고 본문 주소 마이닝 (ETH+SOL)
    run_py("process_defihacklabs.py")        # DeFi 해킹 공격자 (사건 재현 repo)
    run_py("process_poison_phantom.py")      # Poison-Hunter(ETH 오염) + Phantom(SOL 토큰)
    run_py("process_rekt.py")                # rekt.news 사건 공격자 (문맥 판별, 기존 크롤 재처리)

# ---------- 3c) 솔라나 발행사 동결 스캔 (증분) ----------
def sol_freezes():
    run_py("fetch_solana_freezes.py")

# ---------- 3b) 스테이블코인 온체인 동결 스캔 (증분) ----------
def stablecoin():
    run_py("fetch_stablecoin_blacklists.py")

# ---------- 4) 델타 온체인 분류 (SOL) ----------
WALLET_SOURCES = [
    "chainabuse_crawl_SOL.csv", "chainabuse_desc_sol.csv", "allenhark_sol.csv",
    "chainpatrol_blocked.csv", "solphishhunter_sol.csv", "silent_killer_sol.csv",
    "graphsense_sol.csv", "tayvano_lazarus.csv", "kismp_defihack.csv", "rugcheck_creator_sol.csv",
    "solana_frozen_stablecoin.csv",
]

def classify_delta():
    known = set()
    for f in ("sol_types_curated.csv", "sol_types_jcb07.csv", "sol_types_new.csv"):
        p = os.path.join(SOL_VER, f)
        if os.path.exists(p):
            for r in csv.DictReader(open(p, encoding="utf-8")):
                known.add(r["address"])
    todo = set()
    for fn in WALLET_SOURCES:
        p = os.path.join(SRC, fn)
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p, encoding="utf-8")):
            a = (r.get("address") or "").strip()
            if not a or (r.get("chain") or "") != "SOL" or a in known:
                continue
            if re.match(r"^[0-9a-f]+$", a) or not (32 <= len(a) <= 44):
                continue
            todo.add(a)
    print(f"  분류 델타: {len(todo)}개")
    if not todo:
        return
    tgt = os.path.join(RAW, "sol_classify_delta.txt")
    with open(tgt, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(todo)))
    run_py("classify_solana.py", tgt, os.path.join(SOL_VER, "sol_types_new.csv"))

# ---------- 5) 마스터 재빌드 ----------
def rebuild():
    run_py("build_master.py")
    run_py("build_wallets.py")

# ---------- 6) 델타 Etherscan 검증 (키 있을 때만; verify는 자체 이어받기) ----------
def verify():
    key = os.environ.get("ETHERSCAN_KEY", "")
    if not key:
        keyfile = os.path.join(os.path.expanduser("~"), ".etherscan_key")
        if os.path.exists(keyfile):
            key = open(keyfile, encoding="ascii").read().strip()
            os.environ["ETHERSCAN_KEY"] = key
    if not key:
        print("  ETHERSCAN_KEY 없음 — 검증 생략 (미검증 신규분은 COMMUNITY_ONLY로 유지)")
        return
    run_py("verify_etherscan.py", os.path.join(ETH, "master_ethereum.csv"),
           os.path.join(ETH_VER, "etherscan_verify.csv"))

def goplus():
    # 전일 아카이브(미검증분)를 일일 상한만큼 2차 검증 — 락파일로 동시실행 자동 회피
    arch = os.path.join(ETH, "archive_ethereum_community_unverified.csv")
    if not os.path.exists(arch):
        print("  아카이브 없음 — 생략")
        return
    run_py("verify_goplus.py", arch, os.path.join(ETH_VER, "goplus_verify.csv"))

def tiering():
    run_py("build_eth_verified.py")

# ---------- 7) 매니페스트 ----------
def manifest():
    def rows(d, name):
        p = os.path.join(d, name)
        return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []
    sol = rows(SOL, "master_solana_wallets.csv")
    eth_conf = rows(ETH, "master_ethereum_confirmed.csv")
    tiers = Counter()
    p = os.path.join(ETH, "master_ethereum_verified.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            tiers[r["tier"]] += 1
    tokp = os.path.join(SOL, "master_solana_tokens.csv")
    tok = sum(1 for _ in open(tokp, encoding="utf-8")) - 1 if os.path.exists(tokp) else 0
    src = Counter(s for r in sol for s in r["sources"].split("|"))
    m = {
        "generated": date.today().isoformat(),
        "policy": "실제 기반만 (신고·라벨·제재·수사·온체인 사실). 휴리스틱(BFS/wash/ML) 제외.",
        "ethereum_confirmed": {
            "total": len(eth_conf),
            "etherscan_official_malicious": sum(1 for r in eth_conf if r["tier"] == "CONFIRMED_MALICIOUS"),
            "cross_source_confirmed": sum(1 for r in eth_conf if r["tier"] == "CROSS_CONFIRMED"),
            "file": "master_ethereum_confirmed.csv",
        },
        "ethereum_all_tiers": dict(tiers),
        "solana_wallets": {
            "total": len(sol),
            "by_source": dict(src.most_common()),
            "by_onchain_type": dict(Counter(r["onchain_type"] for r in sol)),
            "file": "master_solana_wallets.csv",
        },
        "solana_tokens_separated": {"total": tok, "file": "master_solana_tokens.csv (지갑 아님)"},
        "refresh_failures": failures,
    }
    with open(os.path.join(BASE, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: m[k] for k in ("generated", "ethereum_confirmed", "solana_wallets")},
                     ensure_ascii=False)[:600])

print(f"===== refresh_all 시작: {date.today().isoformat()} =====")
if not NO_CRAWL:
    step("AllenHark 다운로드", dl_allenhark)
    step("dawsbot eth-labels 다운로드", dl_dawsbot)
    step("Chainabuse/ChainPatrol 증분 크롤", crawl)
step("소스 정규화", normalize)
step("스테이블코인 동결 스캔", stablecoin)
step("솔라나 동결 스캔", sol_freezes)
step("SOL 델타 온체인 분류", classify_delta)
step("마스터 재빌드", rebuild)
step("Etherscan 델타 검증", verify)
step("GoPlus 2차 검증 (일일 슬라이스)", goplus)
step("ETH 등급화", tiering)
step("매니페스트", manifest)
print(f"\n===== 완료. 실패 단계: {failures if failures else '없음'} =====")
sys.exit(1 if failures else 0)
