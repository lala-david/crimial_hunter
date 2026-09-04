# 🛡️ Solana 러그풀 탐지기 (Criminal Hunter / detector)

출시 직후(러그 발생 전) 토큰을 **고정밀 블록리스트** 운영점으로 조기 경보하는 탐지기.
우리 실험(`research/`)에서 검증한 신호만 쓰고, 논문이 빠진 **누수 함정**을 피한다.

## 설계 원칙 (실험 근거)

| 원칙 | 근거 |
|---|---|
| **누수 금지** | "총 제거유동성"으로 러그 맞히기는 반칙(제거=러그). 출시 시점 관측 가능 feature만 |
| **동일집단 라벨** | 러그=RugCheck/정상=Jupiter 출처편향(단일 AUC 0.93) → SolRPDS 동일집단 라벨 |
| **시간분할 검증** | 랜덤 CV는 낙관적 → 과거(2021-2023) 학습 → 미래(2024) 테스트 |
| **고정밀 운영점** | 블록리스트는 오탐이 치명 → 정밀도 목표별 도달 재현율로 평가, 확률 보정 |
| **트리 우선** | tabular 최상, 스케일 불필요. NN 불필요 |

## 2-Tier 구조

### Tier-1 — 규칙 기반 (즉시 배포 가능, `detect.py`)
검증된 결정 규칙. 탐지 시점 스냅샷만 필요.
| 규칙 | 러그 검출 | 오탐(FPR) | 출처 |
|---|---|---|---|
| 단일홀더 ≥ 99% | 30.2% | **0.3%** | research/compare |
| 단일홀더 ≥ 95% | 50.4% | **1.1%** | research/compare |
| 단일홀더 ≥ 90% | 69.1% | 3.4% | research/compare |
| mint/freeze 권한 생존 | (보조) | — | 구조 신호 |
| 복합: 홀더≥90% AND 유동성≤$100 | 22.9% | **0.6%** | research/compare |

권한/구조는 `getAccountInfo`(공개 RPC, 지금 가능), 홀더집중은 `getTokenLargestAccounts`(Helius 필요).

### Tier-2 — ML (SolRPDS 라벨 + Helius feature)
- **라벨**: SolRPDS `INACTIVITY_STATUS` (온체인, 동일집단, 11.6만 풀)
- **모델**: XGBoost + isotonic 확률보정, 시간분할, 정밀도≥95% 운영점
- **feature 블록** (전부 누수 없음):
  - A. 권한/구조 — `getAccountInfo` (지금): mint/freeze 권한, Token-2022 확장, decimals, supply
  - B. 홀더집중 — Helius: top1/5/10%, HHI, 홀더수, 인사이더/번들 지분 ← **최강 신호**
  - C. 초기 유동성 — DexScreener+SolRPDS add측: 초기규모, LP수, add 횟수 (제거측 제외)
  - D. 첫 구간 동역학 — Helius tx replay: 첫 1h 매수/매도, 고유매수자, 번들비율
  - E. 생성자 평판 — 이전 배포 수, 과거 러그 이력

## 실험 진행

### ✅ E1 — 누수 없는 베이스라인 (완료, 키 불필요) → `e1_leakfree.py`
add측 feature(add, num_adds, add_per_event)만, 시간분할.
- **AUC 0.840 / PR-AUC 0.547** (기저 러그율 0.20)
- **고정밀 블록리스트: 정밀도 90%+ 도달 불가** (최대 정밀도 ~66%)
- **결론**: 유동성-추가 신호만으론 자동차단 불가 → **홀더집중(Tier-2/Helius)이 필수**임을 실증
- feature 중요도: add_per_event(0.61) > num_adds(0.31). 러그는 회당 미끼 110만 vs 정상 1천

### ✅ Tier-2 잠정 (완료, 키 불필요) → `tier2_now.py`
기존 RugCheck 홀더집중 데이터로 지금 학습, detect.py에 ML 두뇌 연결.
feature = top1_pct·top10_pct·liquidity_usd (전부 추론시점 획득 가능, 결측대체 없음).
- **5-fold CV: AUC 0.947 / PR-AUC 0.986 / MCC 0.697**
- **고정밀 운영점**: 정밀도 99%→재현율 67.6% · **정밀도 95%→재현율 92.9%** · 90%→96.9%
- feature 중요도: top1_pct 0.53 > top10_pct 0.33 > liquidity 0.14
- ⚠️ 학습데이터 출처편향 + 높은 기저율(0.81) → **절대성능 낙관적**. 신호(홀더집중)는
  research/compare에서 독립검증됨(top1≥90%=69%@3.4%FPR). E2로 편향 제거 재학습.

### ⏳ E2 — Helius 홀더집중·첫구간 tx 추가 (키 대기) → `features_helius.py` + `e2_train.py`
SolRPDS **동일집단** 샘플에 Helius로 홀더집중을 추출 → Tier-2를 편향 없이 재학습.
죽은 러그도 pump.fun mint 계정이 살아있어 홀더 조회 가능(생존편향 완화).
이것이 tier2_rugcheck(잠정)를 대체하는 최종 모델.

### ⏳ E3 — ablation (feature 블록별 기여, 누수판 vs 누수없는판 격차)
### ⏳ E4 — 운영점 확정 + 보정 + `detect.py` Tier-2 통합

## 파일
```
detector/
├── README.md            (이 문서 — 설계·진행)
├── e1_leakfree.py       E1: 누수없는 베이스라인 (완료)
├── tier2_now.py         Tier-2 잠정: RugCheck 홀더집중 학습 (완료)
├── detect.py            Tier-1 규칙 + Tier-2 ML 실 mint 채점 (getAccountInfo, Helius-ready)
├── features_helius.py   E2: Helius 홀더집중 추출 (키 대기)
├── e2_train.py          E2: SolRPDS 동일집단 Tier-2 재학습 (키 대기)
└── models/              e1_leakfree.pkl, tier2_rugcheck.pkl (+메트릭 json)
```

## 정직한 한계
가장 강한 신호(홀더집중·첫구간 tx)는 **죽은 러그엔 스냅샷이 없다**(계정 닫힘). Helius tx replay로
pool 히스토리를 되짚어 완화하지만, 완전 복원은 Flipside/Bitquery 히스토리 tx가 이상적(SolRPDS 방식).
