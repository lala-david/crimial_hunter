<div align="center">
<img src="../assets/lena_field.gif" width="360" alt="Lena" />
</div>

# 📡 Sources — 소스별 원천 데이터

모든 파일이 표준 스키마(`address, chain, category, source, label, detail, ref_date`)로 정규화되어 있다.
마스터는 이 파일들을 (chain, address) 기준으로 교차 병합해 만든다. 멀티체인 소스가 있어 한곳에 모아둠.

## 소스 카탈로그

| 파일 | 소스 | 성격 |
|---|---|---|
| `chainabuse_crawl_ETH/SOL.csv` | [Chainabuse](https://chainabuse.com) (TRM Labs) | 피해자 신고 19.6만 건 전량 크롤 |
| `chainabuse_desc_sol.csv` | Chainabuse 신고 본문 | collector·cash-out 지갑 추출 |
| `allenhark_sol.csv` | [AllenHark](https://allenhark.com) | Pump.fun 스캐머 (매일 갱신) |
| `ethlabels_phishhack.csv` / `ethlabels_malicious.csv` | dawsbot/eth-labels | Etherscan 공개 라벨 미러 |
| `scamsniffer_phishing_eth.csv` | ScamSniffer | 피싱 드레이너 (라이브 재수집) |
| `mew_darklist_eth.csv` | MyEtherWallet | 커뮤니티 검증 다크리스트 (라이브 재수집) |
| `forta_eth_malicious.csv` | Forta | 라벨 데이터셋 |
| `stablecoin_blacklist_eth.csv` | 이더리움 온체인 | **USDT/USDC 발행사 동결 이벤트** (tx 해시 보존) |
| `usdt_banned_eth.csv` | (구) 정적 스냅샷 | ↑ 온체인 스캔으로 대체됨 |
| `tayvano_lazarus.csv` / `tayvano_trace_extra.csv` | tayvano 수사 데이터 | 북한 DPRK — 아래 취급 원칙 참고 |
| `kismp_defihack.csv` | kismp | DeFi 해킹 사건 주소 |
| `ofac_sanctions_all.csv` | 미국 OFAC SDN | 제재 (전량 파싱 1,007, 매일 갱신) |
| `gov_law_enforcement_all.csv` | FBI IC3 · Israel NBCTF 등 | 정부·사법기관 |
| `jp_mof_sanctions.csv` | 일본 재무성 | 제재 |
| `ransomwhere_crypto.csv` | Ransomwhere | 랜섬웨어 지급주소 (현재 ETH/SOL 0 — BTC뿐) |
| `cryptoscamdb_eth.csv` | CryptoScamDB | 스캠 DB 아카이브 |
| `graphsense_eth/sol.csv` | GraphSense | 학술 태그팩 |
| `ptxphish_eth.csv` / `yuanqi_eth.csv` | NDSS/학술 | 피싱 연구 데이터 |
| `chainpatrol_blocked.csv` | ChainPatrol | 차단 자산 (ETH+SOL) |
| `solphishhunter_sol.csv` | IEEE TIFS 2026 | 학술 검증 피셔 |
| `silent_killer_sol.csv` | SILENT-KILLER | 포렌식 |
| `solrpds_rugpull_sol.csv` | SolRPDS (CC BY 4.0) | 러그풀 토큰/풀 (지갑 아님) |
| `jupiter_banned_sol.csv` | Jupiter | 차단 토큰 |
| `rugcheck_creator_sol.csv` | RugCheck API | 스캠 토큰 creator 역추출 (개인 배포자만) |
| `kismp_defihack.csv` · `etherscan_blocked_eth.csv` 등 | 기타 큐레이션 | — |

## 🇰🇵 tayvano DPRK 데이터 취급 원칙

자금흐름 추적 데이터는 피해자·거래소·경유지가 혼입될 수 있어 이중 안전장치 적용:

1. 디렉토리 단위 분리 — `tayvano_lazarus`(해킹·절도) / `tayvano_trace_extra`(IT worker 급여지갑 등)
2. 두 소스 모두 교차확인 집계에서 제외(`TAINTED_TRACE`) — **Etherscan 독립 확정 또는 타소스 2+ 일치**로만 confirmed 진입

## 🚫 배제한 소스 (품질 정책)

"추측" 기반은 전부 배제:

| 배제 | 사유 |
|---|---|
| jcb07 Solana-Scam-DB (94,794) | 그래프/BFS 크롤 — 거래상대·일반유저 대량 오탐 |
| Midsummer Meme (44,841) | wash-trading 통계 추정 |
| fesevu, HF ethereum_fraud | ML 활동기반 분류 |
| SolRPDS creator 확장 | 러그풀 판정이 행동 분석 기반 = 휴리스틱 |
| TSLvdd (4,592토큰) | 공용 배포봇 — 스캐머 아님 |

## 라이선스 주의

- OpenSanctions: 상업 이용 시 별도 라이선스
- SolRPDS: CC BY 4.0
- OFAC/FBI: 미 정부 공개자료
- 그 외 각 repo/API 조건 확인 필요
