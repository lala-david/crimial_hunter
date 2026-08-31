# Criminal Hunter — 크립토 스캠 주소 데이터셋 (Solana + Ethereum)

피싱·드레이너·러그풀·해킹·제재 관련 **암호화폐 지갑 주소** 데이터셋. 공개 소스만 수집·정규화하고,
온체인·Etherscan·GoPlus로 검증하여 **실제 기반(신고·라벨·수사·제재·온체인 사실)** 만 남긴 결과.

> **⚠ 이용 안내**: 연구·방어(차단/스크리닝) 목적의 데이터셋입니다. 등급(tier)을 반드시 확인하세요 —
> `CONFIRMED_*`만 고신뢰이며, `COMMUNITY_ONLY`(아카이브)는 미검증 신고라 무고한 주소가 섞일 수 있습니다.
> 원본 소스별 라이선스가 상이하므로(§6) 상업적 이용 전 각 소스 조건을 확인하세요.
> 잘못 포함된 주소 제보는 Issue로 부탁드립니다.

- 최종 갱신: 2026-08-28 — **매일 10:00 자동 갱신** (Windows 작업 스케줄러 `ScamDataRefresh` → `scripts/refresh_all.py`, 로그 `logs/refresh_YYYY-MM-DD.log`)
- 대상 체인: Solana, Ethereum
- 원칙: ① 지갑과 토큰/풀을 분리 ② 휴리스틱(그래프 크롤·wash-trading·ML 추정) 배제 ③ 가능한 한 독립 검증

---

## 1. 최종 산출물 (핵심)

| 파일 | 개수 | 설명 |
|------|------|------|
| **`processed/master_solana_wallets.csv`** | **13,079** | 솔라나 스캠 지갑 (전부 실제 기반) |
| **`processed/master_ethereum_confirmed.csv`** | **23,017** | 이더리움 확정 스캠 (검증 완료) |
| ├ `master_ethereum_etherscan_confirmed.csv` | 21,733 | 그중 Etherscan 공식 악성 (최엄격) |
| `processed/master_solana_tokens.csv` | 101,547 | 솔라나 스캠 **토큰/풀** (지갑 아님·분리 보관) |
| `processed/master_ethereum_verified.csv` | 217,411 | 이더리움 전체 + 검증 컬럼 (감사용 전체본) |
| `processed/archive_ethereum_community_unverified.csv` | 192,981 | 실제 신고·스크랩이지만 Etherscan 미검증 (참고 보관) |

> **요약**: 검증된 스캠 지갑 = 솔라나 **13,079** + 이더리움 **23,017**. (개수는 매일 갱신으로 변동 — 최신 수치는 `processed/MANIFEST.json`)

---

## 2. 스키마

### 솔라나 지갑 (`master_solana_wallets.csv`)
| 컬럼 | 설명 |
|------|------|
| `address` | 지갑 주소 (base58) |
| `chain` | `SOL` |
| `source_count` | 몇 개 독립 소스에 등장했는가 (교차확인 신뢰도) |
| `sources` | 등장 소스 목록 (`\|` 구분) |
| `categories` | 스캠 유형 |
| `onchain_type` | 온체인 판별: `WALLET`(활성 지갑) / `EMPTY`(드레인·폐쇄된 지갑) |
| `ref_date` | 최신 기준일 |

### 이더리움 (`master_ethereum_confirmed.csv` / `_verified.csv`)
| 컬럼 | 설명 |
|------|------|
| `address` | 지갑/컨트랙트 주소 (0x) |
| `source_count`, `sources`, `categories` | 위와 동일 |
| `etherscan_reputation` | Etherscan reputation (2 = 악성 확정) |
| `etherscan_labels` | Etherscan 라벨 (Phish/Hack, Exploit, Poisoning 등) |
| `etherscan_nametag` | Etherscan 네임태그 (예: "Ronin Bridge Exploiter") |
| `tier` | `CONFIRMED_MALICIOUS` / `CROSS_CONFIRMED` / `EXCHANGE_FALSE_POSITIVE` / `COMMUNITY_ONLY` |

---

## 3. 데이터 소스

### 솔라나 (13,079 지갑)
| 소스 | 지갑 수 | 성격 |
|------|--------|------|
| AllenHark | 6,488 | Pump.fun 스캐머 추적 (매일 갱신, `allenhark.com/blacklist.jsonl`) |
| Chainabuse (신고 크롤) | 3,765 | 피해자 실제 신고, 유형별 분류 |
| RugCheck creator | 1,800 | 스캠 토큰 생성자 지갑 (공용 배포봇 제외) |
| tayvano / ZachXBT | 572 | 북한 Lazarus 조사 (hacks-and-thefts 분만, IT worker 제외) |
| Chainabuse 본문 추출 | 398 | 신고 본문 속 collector·cash-out 지갑 |
| ChainPatrol / SolPhishHunter / SILENT-KILLER / kismp / OFAC | ~130 | 큐레이션·학술·포렌식·제재 |

### 이더리움 (confirmed 23,017)

**2026-08-31 확장** — ETH 마스터에 누락돼 있던 라벨 소스 통합 (전량 Etherscan 델타 검증 완료):
- **tayvano (북한 DPRK 수사 데이터)** — `process_tayvano.py`가 두 파일로 분리 추출:
  - `tayvano_lazarus` **13,959** (ETH): `hacks-and-thefts`·`more-hacks-and-thefts` — Lazarus 해킹·절도 추적
  - `tayvano_trace_extra` **301** (ETH만): `dprk-it-workers`(IT worker 급여지갑 — 고용주 등 무고한 상대방 혼입 가능)·`nick-franklin` — **Etherscan rep 2/3 독립 확정(31개)만 confirmed 진입**, 나머지는 라벨 달린 채 아카이브. SOL분은 검증수단이 없어 wallet 마스터 미편입.
  - 두 소스 모두 `TAINTED_TRACE`: 자금흐름 추적 특성상 교차확인 집계에서 제외 — confirmed 진입은 Etherscan 독립 확정 또는 tayvano 외 2+ 소스 일치로만.
- **kismp_defihack ETH 2,541**: DeFi 해킹 사건 주소
- **USDT/USDC 온체인 블랙리스트 3,335** (`fetch_stablecoin_blacklists.py`): Tether AddedBlackList·Circle Blacklisted 이벤트를 Etherscan getLogs로 전수 스캔, 해제 이벤트 상쇄 후 **현재 동결 중**인 주소만 (tx 해시 보존, 매일 증분 스캔). 발행사 집행 조치 = 온체인 사실.
- MEW darklist 라이브 재수집(715, +63) · 번주소/프리컴파일 전역 필터 추가
- SolRPDS 기반 creator 확장은 **불채택** (러그풀 판정이 온체인 행동 분석 기반 = 휴리스틱 성격)
Etherscan 공식 악성 라벨 기준 상위: **Phish/Hack 18,132+** · Poisoning 1,234 · Upbit Hack 815 · Exploit 607 · Heist 133 · Bybit Exploit 63 · Ponzi 50.
원천 소스: Chainabuse, Forta, dawsbot eth-labels, ScamSniffer, MEW ethereum-lists, CryptoScamDB, GraphSense, PTXPhish, yuanqi, OFAC, FBI IC3, Israel NBCTF, Japan MoF, USDT banlist 등.

**dawsbot/eth-labels v1** (2026-08-28 추가): repo가 v1 브랜치로 재구성됨 — `data/csv/accounts.csv`(`address,chainId,label,nameTag`, 멀티체인). `process_ethlabels_v2.py`가 ETH 메인넷 악성 라벨만 추출 → `ethlabels_malicious.csv` **4,232개** (take-action 3,895 · 거래소 exploit 계열 244 · OFAC 127). `blocked`(번주소·프리컴파일 혼입)와 `fraud-proof`(롤업 정상 컨트랙트)는 오탐 위험으로 제외.
→ Etherscan API 델타 검증 결과(2026-08-28): 신규 4,192개 중 **reputation 2(악성 확정) 229개**만 승격, 나머지 3,876개는 rep 0 — take-action 배너는 공식 악성 라벨보다 낮은 경고 단계임이 확인됨. 스크랩 맹신 대신 API 검증을 거치는 정책의 근거.

### 정부·사법기관 (검증된 크립토 주소 공개처)
전 세계 제재 리스트 전수 조사 결과, **크립토 지갑을 기계판독 형태로 공개하는 곳은 미국 OFAC·이스라엘 NBCTF·일본 MoF 뿐**. (EU·UK·UN·우크라이나·캐나다·호주 등은 인물만 제재하고 지갑 주소는 미공개.) 그 외 FBI IC3 PSA(Bybit 51개), UN MSMT 보고서(TRON/BTC), CISA advisory(BTC) 등은 PDF/HTML 본문에만 존재.

---

## 4. 방법론

### 4.1 수집·크롤링
- **Chainabuse**: 프론트엔드 내부 GraphQL 프록시(`chainabuse.com/api/graphql-proxy`)를 찾아 **인증 없이** cursor 페이지네이션으로 전량 수집 — 솔라나 신고 3,520건, 이더리움 신고 193,089건.
- **AllenHark / ChainPatrol / SILENT-KILLER / SolPhishHunter / Jupiter / USDT**: 공개 JSON·CSV·API.
- **tayvano / kismp / GraphSense / CryptoScamDB**: GitHub repo·YAML 파싱으로 주소 추출.
- **RugCheck**: `/v1/tokens/{mint}/report` 로 스캠 토큰의 `creator`(사기꾼 dev 지갑) 역추출.

### 4.2 지갑/토큰 분리 (온체인)
모든 솔라나 주소를 Solana RPC `getMultipleAccounts`로 배치 조회하여 소유 프로그램으로 판별:
- **System Program** → 지갑 (`WALLET`)
- 계정 없음/폐쇄 → 드레인된 지갑 (`EMPTY`)
- **Token / Token-2022** → 토큰 mint (별도 파일로 분리)
- 기타 → 풀/PDA (분리)

→ 토큰 mint·유동성 풀 주소가 "지갑" 목록에 섞이지 않음.

### 4.3 이더리움 검증 (Etherscan + GoPlus 2중 레이어)
Etherscan V2 `getaddresstag` API(100주소/호출)로 전량 조회 → `reputation`·`labels` 확보.
추가로 **GoPlus `address_security`**(무료)로 미검증 아카이브를 2차 검증 (일일 슬라이스 + 대량 배치, `verify_goplus.py`).
- `reputation 2/3` → **CONFIRMED_MALICIOUS** (Phish/Hack·Exploit 등 공식 악성)
- 거래소 라벨(Binance·Deposit Address 등) + reputation 0 → **EXCHANGE_FALSE_POSITIVE** (제외)
- GoPlus 강한 악성 플래그(phishing_activities·stealing_attack·blackmail_activities·cybercrime·sanctioned) → **GOPLUS_CONFIRMED** (독립 2차 라벨; blacklist_doubt·honeypot_related·mixer 같은 의심/연관성 플래그는 불채택)
- 2개+ 소스 교차확인(추적 데이터 제외) → **CROSS_CONFIRMED**
- 나머지 커뮤니티 신고 → **COMMUNITY_ONLY** (메인 제외, 참고 보관)

> **Chainalysis·TRM 관련**: 두 회사의 라벨 DB는 유료 상품이라 공개 덤프가 없음. TRM의 공개 창구가 Chainabuse(전량 크롤 완료)이고, Chainalysis 무료 공개분(제재 오라클/Sanctions API)은 원천이 OFAC → OFAC 원본을 직접 최신화(0xB10C 미러, 일일)로 대체. 우리 SDN 전량 파싱(1,007)이 0xB10C 미러보다 넓음.

### 4.4 품질 정책 — 제외한 것
"추측"에 기반한 소스는 전부 배제 (`[[no-heuristic-scam-sources]]`):
- **그래프/BFS 크롤** (jcb07 Solana-Scam-Wallet-Database, 94,794) — 거래상대·거래소·일반유저 대량 오탐
- **wash-trading 통계 추정** (Midsummer Meme, 44,841)
- **ML 활동기반 분류** (fesevu, HF ethereum_fraud_detection)
- **공용 배포 인프라** (RugCheck creator 중 TSLvdd = 4,592토큰 배포봇)
- **hex 노이즈** (텍스트 파싱 유입 125개)

---

## 5. 실행 방법

### 일상 갱신 (자동/수동)
```bash
python scripts/refresh_all.py            # 전체: 다운로드→증분 크롤→정규화→델타 분류→재빌드→검증→매니페스트
python scripts/refresh_all.py --no-crawl # 크롤 생략, 재빌드만
```
- 매일 10:00 작업 스케줄러 `ScamDataRefresh`가 `scripts/refresh_task.cmd`로 자동 실행.
- 각 단계는 실패해도 다음 단계 진행(이전 산출물 재사용) — 실패 목록은 로그와 `MANIFEST.json`의 `refresh_failures`에 기록.
- Etherscan 검증은 `ETHERSCAN_KEY` 환경변수 또는 `~/.etherscan_key` 파일이 있을 때만 실행 (이어받기 지원 — 신규분만 조회).
- **주의**: `crawl_chainabuse.py`의 오프셋 이어받기는 최초 전량 수집용. 목록이 최신순이라 갱신에 쓰면 신규 신고를 놓침 → 갱신은 `refresh_chainabuse.py`(front-fill: 앞에서부터 아는 report id 연속 3페이지 만날 때까지) 사용.

### 최초 전량 구축 (참고)
```bash
# 1) 크롤링 (Chainabuse SOL/ETH, ChainPatrol)
python scripts/crawl_chainabuse.py SOL
python scripts/crawl_chainabuse.py ETH
python scripts/crawl_chainpatrol.py

# 2) 소스 정규화
python scripts/process.py              # 공개 데이터셋
python scripts/process_gov.py          # 정부·사법기관 + OFAC 국가분해
python scripts/process_extra.py        # ChainPatrol/AllenHark/SolPhish/Jupiter/dawsbot(구)
python scripts/process_academic.py     # CryptoScamDB/yuanqi/PTXPhish/SILENT-KILLER
python scripts/process_chainabuse_crawl.py   # 크롤 → 주소 단위 카테고리화
python scripts/process_ethlabels_v2.py       # dawsbot v1 악성 라벨

# 3) 온체인 분류 (지갑/토큰)
python scripts/classify_solana.py <주소목록> <출력csv>

# 4) creator 역추출 (선택)
python scripts/resolve_creators.py raw/rugcheck_targets_valid.txt processed/rugcheck_creators.csv

# 5) 마스터 빌드
python scripts/build_master.py         # 이더리움 교차출처 병합
python scripts/build_wallets.py        # 솔라나 지갑 전용 (토큰 분리)

# 6) 이더리움 검증
ETHERSCAN_KEY=<키> python scripts/verify_etherscan.py processed/master_ethereum.csv processed/etherscan_verify.csv
python scripts/build_eth_verified.py   # Etherscan 등급화 (+ 아카이브 재생성)
```

> `finalize.py`/`make_manifest.py`는 구세대 스키마 기준의 잔재 — 실행하지 말 것. 매니페스트는 `refresh_all.py`가 생성.

---

## 6. 한계 및 주의사항

- **이더리움**은 Etherscan 공식 라벨로 **독립 검증**됨 → 20,465개는 확실.
- Etherscan 키는 `~/.etherscan_key` 파일에서 자동 로드. 이 키는 조회형(`getaddresstag`)만 가능 — 라벨별 전수 추출(`exportaddresstags`, `api-metadata.etherscan.io`)은 Enterprise 전용이라 "Access not allowed".
- **솔라나는 Etherscan 같은 권위 라벨 API가 없음**. GoPlus·기타도 솔라나는 토큰 검사만 지원(주소 악성판정 불가). 따라서 솔라나 13,196개는 **출처 신뢰도 기반**이며 독립 검증은 불가 — 전부 실제 신고·라벨·수사·제재·온체인 creator에서 왔지만, ETH 수준의 확정성은 아님.
- **라이선스 상이**: OpenSanctions는 상업 이용 시 별도 라이선스, SolRPDS는 CC BY 4.0, OFAC/FBI는 미 정부 공개자료. 사용 전 각 소스 라이선스 확인 필요.
- `EMPTY`(드레인된 지갑)는 자금이 이미 빠져나간 상태 — 차단엔 유효하나 잔액 추적엔 무의미.
- 커뮤니티 신고(Chainabuse)는 모더레이터 검증 전이라 드물게 피해자·거래소 주소가 섞일 수 있음.

---

## 7. 파일 구조

```
scam-address-data/
├── README.md
├── raw/                          # 원본 다운로드 (Chainabuse jsonl, OFAC xml, repo 등)
├── processed/
│   ├── master_solana_wallets.csv          ★ 솔라나 지갑
│   ├── master_solana_tokens.csv           솔라나 토큰/풀 (분리)
│   ├── master_ethereum_confirmed.csv      ★ 이더리움 confirmed
│   ├── master_ethereum_etherscan_confirmed.csv   Etherscan 악성 (최엄격)
│   ├── master_ethereum_verified.csv       이더리움 전체 (감사)
│   ├── archive_ethereum_community_unverified.csv  미검증 신고 (참고)
│   ├── <source>_*.csv                     소스별 개별 정규화본
│   └── MANIFEST.json                      최신 수치·소스분포 (refresh_all이 갱신)
├── logs/                         # 자동 갱신 로그 (refresh_YYYY-MM-DD.log)
└── scripts/                      # 파이프라인 스크립트
    ├── refresh_all.py            ★ 전체 갱신 오케스트레이터 (스케줄러가 매일 실행)
    ├── refresh_chainabuse.py     Chainabuse 증분 크롤 (front-fill)
    ├── refresh_task.cmd          작업 스케줄러 러너
    ├── process_ethlabels_v2.py   dawsbot v1 악성 라벨 정규화
    └── (crawl_*, process_*, classify_*, build_*, verify_* — 상단 5절 참고)
```
