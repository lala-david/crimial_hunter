# -*- coding: utf-8 -*-
"""솔라나 주소를 온체인 owner로 분류: WALLET / TOKEN / PROGRAM / EMPTY.
사용법: python classify_solana.py <입력파일(1줄1주소)> <출력csv>
- base58(32바이트) 사전검증으로 무효주소 배제, getMultipleAccounts(100), 이어받기 지원
- 공개 RPC는 mainnet-beta만 안정 → 레이트리밋 백오프로 처리
"""
import csv, json, os, sys, time, urllib.request

SRC, DST = sys.argv[1], sys.argv[2]
RPC = "https://api.mainnet-beta.solana.com"
SYS = "11111111111111111111111111111111"
TOKENS = {"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
          "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"}

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
IDX = {c: i for i, c in enumerate(ALPH)}

def valid_pubkey(s):
    if not (32 <= len(s) <= 44):
        return False
    n = 0
    for c in s:
        if c not in IDX:
            return False
        n = n * 58 + IDX[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return len(b"\x00" * pad + body) == 32

def classify(owner, exists):
    if not exists:
        return "EMPTY"       # 계정 없음/닫힘 — 드레인된 지갑 후보
    if owner == SYS:
        return "WALLET"
    if owner in TOKENS:
        return "TOKEN"
    return "PROGRAM"         # 풀/컨트랙트/PDA

def rpc(batch):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
                       "params": [batch, {"encoding": "base64"}]}).encode()
    delay = 2
    for attempt in range(9):
        try:
            req = urllib.request.Request(RPC, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            if "result" in d:
                return d["result"]["value"]
            # error(대개 429 레이트리밋) → 백오프
            time.sleep(delay); delay = min(30, delay * 1.7)
        except Exception:
            time.sleep(delay); delay = min(30, delay * 1.7)
    return None

# 사전검증 + 이어받기
done = set()
if os.path.exists(DST):
    with open(DST, encoding="utf-8") as f:
        done = {r["address"] for r in csv.DictReader(f)}
targets, skipped = [], 0
with open(SRC, encoding="utf-8") as f:
    for line in f:
        a = line.strip()
        if not a or a in done:
            continue
        if valid_pubkey(a):
            targets.append(a)
        else:
            skipped += 1
print(f"분류 대상 {len(targets)} (완료 {len(done)}, 무효배제 {skipped})")

mode = "a" if done else "w"
out = open(DST, mode, newline="", encoding="utf-8")
w = csv.writer(out)
if not done:
    w.writerow(["address", "type", "owner"])

from collections import Counter
dist = Counter()
for i in range(0, len(targets), 100):
    batch = targets[i:i + 100]
    vals = rpc(batch)
    if vals is None:
        print(f"  배치 {i} RPC 실패 — 30s 후 재시도")
        time.sleep(30)
        vals = rpc(batch)
        if vals is None:
            print(f"  배치 {i} 재실패 — 스킵")
            continue
    for addr, v in zip(batch, vals):
        exists = v is not None
        owner = v["owner"] if exists else ""
        t = classify(owner, exists)
        dist[t] += 1
        w.writerow([addr, t, owner])
    out.flush()
    if (i // 100) % 10 == 0:
        print(f"  {i+len(batch)}/{len(targets)}  {dict(dist)}")
    time.sleep(0.3)
out.close()
print(f"완료: {dict(dist)}")
