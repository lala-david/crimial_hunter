<div align="center">
<img src="../assets/lena_command.gif" width="340" alt="Lena" />
</div>

# 🔬 솔라나 러그풀 메커니즘 — 온체인 실행과 탐지 데이터

러그풀이 **온체인에서 정확히 어떻게 일어나는지**, **탐지에 어떤 온체인 데이터가 필요한지**, 그리고 **우리가 뭘 더 수집·분석해야 하는지**를 이론 리서치 + 우리 러그 토큰 1,199개 실측으로 종합.

**한 줄 결론**: 요즘 솔라나 러그는 권한 남용(무한발행·허니팟)이 아니라 **"물량 독점 후 덤프"가 86%** — 우리 데이터가 이를 실증한다.

---

## 1. 러그풀 5대 메커니즘 (온체인 실행)

**핵심 구조**: pump.fun 본딩커브는 **설계상 하드러그가 불가능**(개발자가 커브 유동성을 뺄 프로그램 경로가 없음). 따라서 pump.fun 러그는 거의 전부 **개발자 덤프(소프트러그)**. 하드러그(LP 걷어가기)는 개발자가 인출 가능 LP를 쥔 Raydium/Orca 풀에서만 발생.

| 유형 | 온체인 실행 | 안전 신호 |
|---|---|---|
| **개발자 덤프 (소프트러그)** | 생성 슬롯에 바닥가 대량 매수 → 후발자 SOL을 `sell` 스왑으로 회수 (수명 중앙값 ~14분) | top1/top10 집중도 낮음 |
| **유동성 걷어가기 (하드러그)** | LP 보유자가 Raydium `Withdraw`(idx 4)/Orca `decreaseLiquidity` → LP 소각 + vault 자산 회수 | LP 소각(`1nc1nerator…`)/잠금 |
| **허니팟** | freeze authority로 매도 계정 동결 / Token-2022 transfer fee 100% / transfer hook 블랙리스트 | freeze authority 포기 |
| **무한 발행** | mint authority로 `MintTo` 반복 → 풀에 덤프 | mint authority 포기 |
| **인사이더/번들** | Jito 번들로 여러 지갑에 물량 분산, "유기적" 위장 | 인사이더 supply 낮음 |

pump.fun 프로그램 `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` · BondingCurve PDA `["bonding-curve", mint]` · 졸업 조건 `real_token_reserves==0`(시총 ~$69k) → PumpSwap 마이그레이션(LP 소각).

---

## 2. 우리 데이터 실측 (러그 토큰 1,199개, RugCheck 온체인)

이론을 우리 데이터로 검증한 결과 — **정확히 일치**:

### 주 메커니즘 분류 (배타)
| 유형 | 비율 |
|---|---:|
| **개발자 독점 덤프 (top1≥80%)** | **85.9%** |
| 기타/저유동성 | 12.1% |
| 인사이더 | 1.9% |
| 허니팟 | 0.1% |
| 무한발행 | 0.0% |
| 유동성 인출(하드러그) | 0.0%* |

### 핵심 시그널 출현율
- **소수 독점 (top10 ≥ 90%): 90.7%** ← 최강 시그널
- 개발자 독점 (top1 ≥ 90%): 69.9%
- 유동성 없음 (< $100): 25.0%
- 인사이더 네트워크 탐지: 2.9%
- **권한 포기율: mint 100.0% / freeze 99.9%**

### 해석
1. **"물량 독점"이 러그의 본질** — top10이 90% 이상 쥔 경우가 91%. 이게 유형을 관통하는 단일 지표.
2. **권한 남용은 사실상 소멸** — mint authority 100%, freeze authority 99.9%가 포기 상태. pump.fun이 자동 포기시키므로 무한발행·허니팟 러그는 거의 불가능. "요즘 러그 = 선보유 덤프"라는 리서치 주장을 실증.
3. **위험 태그 1위 = Low Liquidity (47.3%)**, 2위 = Top 10 holders high ownership (21.3%).

*하드러그 0%는 **생존 편향** — 우리 샘플은 RugCheck가 인식하는 "살아있는" mint(커브 단계 소프트러그 위주). 이미 유동성이 빠져 계정이 닫힌 완료 하드러그는 조회 자체가 안 됨(`closed`).

---

## 3. 탐지에 필요한 온체인 데이터 TOP 10

| # | 데이터 | 획득 방법 | 판별 대상 |
|---|---|---|---|
| 1 | **freeze authority 상태** | `getAccountInfo` parsed | 허니팟 |
| 2 | **mint authority 상태** | `getAccountInfo` parsed | 무한발행 |
| 3 | **LP 소각/잠금 비율** | `getTokenSupply(lpMint)` vs 풀 reserve | 하드러그 |
| 4 | **상위 홀더 집중도** (커브 PDA 제외) | `getTokenLargestAccounts` + `getTokenSupply` | 물량 독점 ⭐ |
| 5 | 번들/스나이퍼 supply 점유 | 같은 슬롯 다중 buy 클러스터링 | 인사이더 |
| 6 | 인사이더 펀딩 그래프 | 홀더 owner → 공통 SOL 펀더 추적 | 은닉 집중 |
| 7 | 유동성 규모·변화 | DexScreener/GeckoTerminal API | TVL rug |
| 8 | 개발자 매도·유동성 인출 이벤트 | Helius Enhanced tx (SWAP/WITHDRAW_LIQUIDITY) | 러그 실행 순간 |
| 9 | 비활성 비율·토큰 수명 | `getSignaturesForAddress` blockTime | idle rug |
| 10 | **creator 과거 러그 이력** | Bitquery pump `create` by signer | 재범 (러그 94%가 동일 배포주소) |

---

## 4. 우리가 더 수집·분석해야 할 것 (실측이 드러낸 gap)

실측에서 나온 **판별 공백**을 메우는 게 다음 우선순위:

1. **인사이더 클러스터링** (최우선) — top1≥90%가 69.9%인데 인사이더 탐지는 2.9%뿐. 즉 **물량을 여러 지갑에 쪼갠 번들형을 못 잡음**. 홀더 owner 열거 → 각 지갑의 최초 SOL 펀더(`getSignaturesForAddress`→`getTransaction`) 추적 → 공통 펀더 클러스터 식별 필요. (Bubblemaps "Gas Rule" 방식)
2. **creator 발행 이력** — 러그의 94%가 동일 배포주소인데 우리 creator 재범은 0.8%(RugCheck creatorTokens 제한적). Bitquery로 creator의 전체 `create` 이력 → 형제 러그 토큰 라벨링.
3. **완료된 하드러그 복원** — 생존 편향 보정. 계정 닫힌 mint의 온체인 tx 히스토리(LP `Withdraw` 이벤트)로 완료 러그를 별도 수집.
4. **시계열 (생성→러그 시각)** — 러그 수명 중앙값 14분. 현재 스냅샷만 있음. 첫 5분 거래 미세구조가 예측력 최강(Catching the Rug 23-feature).

### 데이터셋 라벨링 표준 (우리 "휴리스틱 배제" 원칙과 부합)
**SolRugDetector(arXiv 2603.24625)** 방식 = freeze 명령·LP 인출·잔고 단조감소 같은 **검증 가능한 온체인 사실**로 라벨링. BFS/wash/ML 추론이 아니므로 채택 가능. FPR 0.26%, 100,063개 중 76,469 러그 확증. → 우리가 SolRPDS creator 확장을 "휴리스틱"이라 거부한 것과 달리, **온체인 사실 기반 행위 라벨링**은 원칙에 맞음.

---

## 참고 문헌
SolRPDS (CODASPY 2025, arXiv:2504.07132) · Catching the Rug (arXiv:2608.20271) · MemeTrans (arXiv:2602.13480) · SolRugDetector (arXiv:2603.24625) · Sniper 코호트 (arXiv:2607.02795) · Graduation 생존분석 (arXiv:2607.02823) · SoK Rug Pull (arXiv:2403.16082) · Solidus Labs·Chainalysis·Merkle Science 리포트 · pump.fun docs · Helius/RugCheck/Birdeye/DexScreener/Bitquery API.

## 재현
```bash
python research/collect_mechanism.py <mint목록> research/mechanism_features.csv 1200
python research/analyze_mechanism.py
```
데이터: `mechanism_features.csv` (러그 토큰 1,199개 온체인 메커니즘 특징).
