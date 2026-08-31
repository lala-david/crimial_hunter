<div align="center">
<img src="../../assets/lena_sunset.gif" width="360" alt="Lena" />
</div>

# ⛓️ Solana 온체인 분류 캐시

솔라나 주소를 RPC로 조회해 **지갑인지 토큰인지** 판별한 결과 캐시.
[`build_wallets.py`](../../scripts/build_wallets.py)가 이걸 읽어 지갑/토큰 마스터를 분리 생성한다.
**이어받기용 캐시라 삭제하면 전량 재조회가 필요하니 주의.**

## 파일

| 파일 | 내용 |
|---|---|
| `sol_types_curated.csv` | 큐레이션 소스 주소들의 온체인 판별 |
| `sol_types_jcb07.csv` | (배제된 BFS 소스의 판별 캐시 — 마스터엔 미사용, 캐시만 보존) |
| `sol_types_new.csv` | 신규 유입분 판별 (매일 델타 분류가 여기에 append) |
| `rugcheck_creators.csv` | RugCheck API로 역추출한 토큰 mint → creator 지갑 매핑 |

## 판별 기준 (`type` 컬럼)

RPC `getMultipleAccounts`의 소유 프로그램(owner) 기준:

| 값 | 의미 | 처리 |
|---|---|---|
| `WALLET` | System Program 소유 = 일반 지갑 (활성) | 지갑 마스터 |
| `EMPTY` | 계정 없음/폐쇄 = 드레인된 지갑 | 지갑 마스터 |
| `TOKEN` | Token/Token-2022 프로그램 = 토큰 mint | 토큰 파일로 분리 |
| `PROGRAM` | 그 외 프로그램 소유 = 풀/컨트랙트/PDA | 토큰 파일로 분리 |

## 갱신

매일 자동 갱신 때 소스에 새로 등장한 주소만 델타 분류 → `sol_types_new.csv`에 append.
