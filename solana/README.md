<div align="center">
<img src="../assets/lena_smile.gif" width="360" alt="Lena" />
</div>

# 🟣 Solana 스캠 주소

**지갑과 토큰/풀을 온체인으로 판별해 분리**한 데이터. 모든 주소를 Solana RPC
`getMultipleAccounts`로 조회해 소유 프로그램 기준으로 분류했다 — 토큰 mint가 "스캐머 지갑"에 섞이지 않음.

## 파일

| 파일 | 개수 | 용도 |
|---|---:|---|
| **`master_solana_wallets.csv`** | 13,079 | 🥇 **스캠 지갑 (차단/스크리닝용)** |
| `master_solana_tokens.csv` | 101,547 | 🪙 스캠 토큰 mint·유동성 풀 (지갑 아님 — 토큰 필터링용) |
| `master_solana.csv` | — | 병합 원본 (파이프라인 중간산출) |
| `verify/` | — | 온체인 분류 캐시 (`sol_types_*`) · RugCheck creator 캐시 |

## 스키마 (`master_solana_wallets.csv`)

| 컬럼 | 설명 |
|---|---|
| `address` | 지갑 주소 (base58) |
| `source_count` | 등장한 독립 소스 수 |
| `sources` | 소스 목록 (`\|` 구분) |
| `categories` | 스캠 유형 (scammer_pumpfun, phishing, rugpull_dev_creator, state_actor_dprk …) |
| `onchain_type` | `WALLET` 활성 지갑 / `EMPTY` 드레인·폐쇄된 지갑 |
| `ref_date` | 최신 기준일 |

## 소스 구성

| 소스 | 지갑 수 | 성격 |
|---|---:|---|
| AllenHark | 6,488 | Pump.fun 스캐머 추적 (매일 갱신) |
| Chainabuse 신고 크롤 | 3,765 | 피해자 실제 신고 |
| RugCheck creator 역추출 | 1,800 | 스캠 토큰 생성자 지갑 (공용 배포봇 제외) |
| tayvano / ZachXBT | 572 | 북한 Lazarus 조사 (해킹·절도 분만) |
| Chainabuse 본문 추출 | 398 | 신고 본문 속 collector·cash-out 지갑 |
| ChainPatrol · SolPhishHunter · SILENT-KILLER · kismp · OFAC | ~130 | 큐레이션·학술·포렌식·제재 |

## 한계

- **솔라나엔 Etherscan급 권위 라벨 API가 없음** (GoPlus도 솔라나는 토큰 검사만 지원)
  → 이 목록은 **출처 신뢰도 기반**이며 이더리움 수준의 독립 확정은 아님.
  전부 실제 신고·라벨·수사·제재·온체인 creator에서 왔다.
- `EMPTY`(드레인된 지갑)는 자금이 이미 빠져나간 상태 — 차단엔 유효, 잔액 추적엔 무의미.
