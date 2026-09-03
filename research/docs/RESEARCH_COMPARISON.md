<div align="center">
<img src="../assets/lena.gif" width="340" alt="Lena" />
</div>

# 📚 학계 러그풀 연구 vs 우리 데이터셋 — 정밀 비교

솔라나 러그풀 논문 6편 전문(arXiv PDF)을 다운받아 정독하고, 우리 프로젝트(Criminal Hunter)와 데이터·방법론을 정확히 비교했다.

**한 줄 결론**: 6편 모두 라벨을 **휴리스틱/규칙/신고+수동**으로 생성한다(ML은 예측용, 라벨 추론용 아님) → 우리 "휴리스틱 배제, 실근거만" 원칙과 일치. 그중 **From Hype to Collapse**가 방법론적으로 우리와 가장 가깝고, **SolRPDS는 우리가 이미 소비·검증한 원본**이다.

---

## 1. 6편 논문 요약

| 논문 | 규모 | 기간 | 라벨 방법 | 데이터 출처 | 모델 | 주소 공개 |
|---|---|---|---|---|---|---|
| **SolRPDS** (2504.07132, CODASPY'25) | 62,895 풀 / 33,746 토큰 | 2021.2–2024.11 | inactivity(유동성제거후 거래중단) | Flipside SQL | ML 6종 (AdaBoost 97.6%) | 풀·mint |
| **Catching the Rug** (2608.20271) | **640만 토큰**, ~10억 tx | 2024.11–2025.6 | TVL −99% 낙폭 OR 유휴>수명80% | 직접 RPC/노드 | ML (XGBoost MCC 0.39) | ✗ |
| **From Hype to Collapse** (2603.24625, 中山대) | 100,063→**76,469 라벨** + 벤치 117 | 2025 상반기 | **freeze남용/유동성인출/pump-dump 규칙 + 수동검증 (FP 0.26%)** | **Chainabuse+RPC+Solscan** | 없음(측정연구) | **주소+유형** |
| **MELT/MemeTrans** (2602.13480, GeorgiaTech) | 41,470 런치, 2.19억 tx | 2024.12–2025.3 | 마이그후 20분 min_price_ratio<0.3 OR 조작 | 온체인+Jito번들 | ML (MLP+LSTM AUPRC 0.58) | ✗ |
| **Sniper Cohorts** (2607.02795) | 2,965 지갑 / 166k 런치 | 2026.6 (13일) | co-occurrence union-find (스캠 아님 명시) | 직접 노드 | 휴리스틱+PSM | **지갑 2,965** |
| **Graduation** (2607.02823) | 832,941 런치 | 2026.5–6 | 없음(졸업 생존분석) | pump.fun API | Cox 회귀 | ✗ (mint만) |

## 2. 우리(Criminal Hunter)와의 핵심 차이

| 축 | 학계 논문들 | 우리 |
|---|---|---|
| **목적** | 단일 연구 (데이터셋 or 탐지기 or 측정) | 실전 방어용 블록리스트 |
| **대상** | 대부분 토큰/풀 중심 | **지갑 + 토큰/풀 분리** (스캐머 지갑도) |
| **체인** | 솔라나만 | **솔라나 + 이더리움** |
| **라벨 근거** | 단일 방법(온체인 규칙 or 가격) | **다중소스**(신고·제재·수사·라벨) + 온체인 검증 |
| **검증** | 논문 내부 검증 | **DexScreener 유동성·Etherscan·GoPlus 교차검증** |
| **SolRPDS 관계** | SolRPDS = 원본 생산 | **SolRPDS를 소비→온체인 재검증→오탐 제거** |

## 3. 논문별 우리와의 관계

**SolRPDS (우리 데이터 원본)**
- 그들: Flipside SQL로 유동성 집계 → inactivity 라벨(저자도 "신호일 뿐 확정 아님"). ML로 active/inactive 분류.
- 우리: 그 풀/mint를 가져와 **DexScreener로 실제 유동성 검증 → 94.6% 러그 확정, 오탐 155개 제거**. 그들의 "의심"을 "온체인 사실"로 업그레이드. (논문 future work "on-chain detection tested against historical events"를 우리가 실행)

**From Hype to Collapse (가장 유사, 배울 점 많음)**
- 그들: **Chainabuse 신고 + 온체인 3유형 규칙(freeze남용/유동성인출/pump-dump) + 수동검증, FP 0.26%**. 우리 방법론과 거의 동일 철학.
- 우리가 배울 것: 그들의 **3유형 라벨링 규칙**이 우리 풀 검증을 더 정교하게 만들 수 있음 (지금은 유동성 유무만, 그들은 freeze/withdrawal/pump-dump 구분). ITW-76469 주소셋은 교차확인 소스로도 활용 가능.

**MELT (번들 추적 = 우리 gap 채움)**
- 그들: **공급의 36.5%가 번들(조율) 계정 보유**를 3소스(다계정 공동매수/자금흐름/Jito번들)로 폭로. 122 feature.
- 우리가 배울 것: 우리 메커니즘 분석에서 "top1≥90%는 69%인데 인사이더 탐지는 2.9%뿐"(번들형 못 잡음)이 gap이었는데, **MELT의 번들 추적 방법(공통 자금흐름 + Jito bundle)**이 정확히 그 해법.

**Catching the Rug (사전 탐지)**
- 그들: **첫 5분 거래로 1시간 러그 예측** (XGBoost MCC 0.39, 23 feature). 우리 조기감지 연구와 방향 일치.
- 우리가 배울 것: 우리는 스냅샷 기반인데, 그들의 **시계열 첫-5분 feature**가 실시간 사전탐지에 필요.

**Sniper Cohorts / Graduation (참고만)**
- Sniper 2,965 지갑은 co-occurrence 휴리스틱(스캠 아님 명시) → 라벨엔 부적합, "봇 제외 리스트"로만.
- Graduation은 "market cap(가상리저브) ≠ 실제 자본" 경고가 실무상 유용 (온체인 상태는 `complete`·`real_sol_reserves`로 봐야 함).

## 4. 종합 — 우리의 위치

- **우리는 학계 데이터셋(SolRPDS)의 소비자이자 검증자**다. 학계가 "의심 풀 6.3만"을 SQL+ML로 만들면, 우리는 온체인 유동성으로 "러그 확정 6만 + 오탐 제거 + 스캠코인 역추출"로 정제한다.
- **From Hype to Collapse가 우리의 방법론적 사촌**이다 — 둘 다 신고+온체인규칙+수동검증, 휴리스틱/ML추론 배제. 그들의 3유형 라벨링을 채택하면 우리 풀 검증이 정교해진다.
- **다음 단계 3가지** (논문에서 도출):
  1. 풀 검증에 **freeze남용/유동성인출/pump-dump 3유형 구분** 추가 (From Hype to Collapse)
  2. **번들/인사이더 추적** (공통 자금흐름 + Jito bundle) 으로 top-holder 우회 케이스 잡기 (MELT)
  3. **첫 5분 시계열 feature** 로 실시간 사전탐지 (Catching the Rug)

---

*논문 PDF·텍스트: `raw/papers/*.{pdf,txt}` (gitignore — 저작권). arXiv: 2504.07132, 2608.20271, 2603.24625, 2602.13480, 2607.02795, 2607.02823.*
