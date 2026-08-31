# -*- coding: utf-8 -*-
"""USDT/USDC 온체인 블랙리스트 수집 — Etherscan getLogs로 동결/해제 이벤트 전수 스캔.
Tether AddedBlackList/RemovedBlackList, Circle Blacklisted/UnBlacklisted.
마지막 이벤트가 '동결'인 주소만 채택 (현재 동결 상태). 실제 발행사 집행 조치 = 온체인 사실.
- 증분: raw/stablecoin_logs_state.json 에 계약·이벤트별 마지막 스캔 블록 저장
- 이벤트 원본: raw/stablecoin_events.jsonl (append)
출력: processed/stablecoin_blacklist_eth.csv
"""
import csv, json, os, time, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "processed")
STATE = os.path.join(RAW, "stablecoin_logs_state.json")
EVENTS = os.path.join(RAW, "stablecoin_events.jsonl")

key = os.environ.get("ETHERSCAN_KEY", "")
if not key:
    kf = os.path.join(os.path.expanduser("~"), ".etherscan_key")
    if os.path.exists(kf):
        key = open(kf, encoding="ascii").read().strip()
if not key:
    raise SystemExit("ETHERSCAN_KEY 필요")

USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
# (계약, topic0, 이벤트명, 동결여부, 주소위치 data/topic1, 시작블록)
SCANS = [
    (USDT, "0x42e160154868087d6bfdc0ca23d96a1c1cfa32f1b72ba9ba27b69b98a0d819dc", "AddedBlackList",   True,  "data",   4634748),
    (USDT, "0xd7e9ec6e6ecd65492dce6bf513cd6867560d49544421d0783ddf06e76c24470c", "RemovedBlackList", False, "data",   4634748),
    (USDC, "0xffa4e6181777692565cf28528fc88fd1516ea86b56da075235fa575af6a4b855", "Blacklisted",      True,  "topic1", 6082465),
    (USDC, "0x117e3210bb9aa7d9baff172026820255c6f6c30ba8999d1c2fd88e2848137c4e", "UnBlacklisted",    False, "topic1", 6082465),
]

def api(params):
    url = "https://api.etherscan.io/v2/api?chainid=1&" + params + "&apikey=" + key
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode())
            # getLogs: status 0 + "No records found" 는 정상 빈결과
            if d.get("status") == "1" or "No records" in str(d.get("message", "")) \
               or str(d.get("result", ""))[:1] == "0" and "jsonrpc" in d:
                return d
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None

d = api("module=proxy&action=eth_blockNumber")
if d is None or not d.get("result"):
    raise SystemExit("eth_blockNumber 실패")
HEAD = int(d["result"], 16)
print(f"현재 블록: {HEAD:,}")

state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}

def extract_addr(log, where):
    if where == "topic1" and len(log.get("topics", [])) > 1:
        return "0x" + log["topics"][1][-40:]
    return "0x" + log["data"][-40:]

ev_out = open(EVENTS, "a", encoding="utf-8")
for contract, topic, name, is_freeze, where, deploy_block in SCANS:
    skey = f"{contract[:10]}:{name}"
    frm = state.get(skey, deploy_block)
    total = 0
    span = 2_000_000
    print(f"[{name}] {frm:,} -> {HEAD:,}")
    while frm <= HEAD:
        to = min(frm + span, HEAD)
        d = api(f"module=logs&action=getLogs&address={contract}&topic0={topic}"
                f"&fromBlock={frm}&toBlock={to}")
        if d is None:
            raise SystemExit(f"  {name}: {frm} 범위 반복 실패 — 중단(다음 실행 때 재개)")
        logs = d.get("result") or []
        if not isinstance(logs, list):
            logs = []
        if len(logs) >= 1000:      # 캡 도달 — 잘렸을 수 있으니 범위 반으로
            span = max(10_000, span // 2)
            continue
        for lg in logs:
            ev_out.write(json.dumps({
                "event": name, "freeze": is_freeze,
                "address": extract_addr(lg, where),
                "block": int(lg["blockNumber"], 16),
                "time": int(lg["timeStamp"], 16),
                "tx": lg["transactionHash"],
            }) + "\n")
        total += len(logs)
        frm = to + 1
        state[skey] = frm
        if len(logs) < 200:
            span = min(4_000_000, span * 2)
        time.sleep(0.25)
    print(f"  신규 이벤트 {total}건")
    json.dump(state, open(STATE, "w", encoding="utf-8"))
ev_out.close()

# ---- 이벤트 → 현재 동결 상태 재구성 (주소별 마지막 이벤트 기준) ----
last = {}   # (coin, addr) -> (block, freeze, time)
with open(EVENTS, encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        coin = "USDT" if e["event"].endswith("BlackList") else "USDC"
        k = (coin, e["address"].lower())
        if k not in last or e["block"] >= last[k][0]:
            last[k] = (e["block"], e["freeze"], e["time"])

BURN = {"0x" + "0" * 40} | {f"0x{'0'*39}{i}" for i in "123456789"} | {"0x000000000000000000000000000000000000dead"}
rows = []
for (coin, addr), (blk, freeze, ts) in sorted(last.items()):
    if not freeze or addr in BURN:
        continue
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    src = "usdt_banned" if coin == "USDT" else "usdc_banned"
    rows.append([addr, "ETH", "enforcement_frozen", src,
                 f"{coin} blacklisted onchain", f"block={blk}", day])

with open(os.path.join(OUT, "stablecoin_blacklist_eth.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["address", "chain", "category", "source", "label", "detail", "ref_date"])
    w.writerows(rows)
from collections import Counter
print(f"-> stablecoin_blacklist_eth.csv: {len(rows)}개 (현재 동결 중)  {dict(Counter(r[3] for r in rows))}")
