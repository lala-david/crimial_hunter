<div align="center">
<img src="../assets/lena_command.gif" width="340" alt="Lena" />
</div>

# 🧮 러그풀 탐지 기술 명세 — 논문별 수식·임계값·알고리즘

인용·급 높은 러그풀 논문 7편의 PDF를 다운받아 **모든 수식·임계값(기준점)·feature·모델을 정확히 추출**했다. 우리가 그대로 구현할 수 있는 형태로 정리.

## ⭐ 핵심 결론 — 이 분야는 임베딩/딥러닝을 안 쓴다

**어떤 논문도 node2vec·GNN·graph embedding·TF-IDF 같은 표현학습을 라벨링에 쓰지 않는다.**
- Mazorra는 그래프를 **스칼라 통계량**(HHI, clustering coefficient)으로 축약 — 제목이 "zero-dimensional"인 이유
- MELT는 명시적으로 "**no graph models**" — 번들 관계(계정 그래프)를 토큰 단위 feature로 distill
- 라벨링은 전부 **결정론적 온체인 규칙 + 임계값**, 예측은 **트리 모델(XGBoost/RF)이 뉴럴넷을 일관되게 능가**

→ 우리 원칙(휴리스틱/ML추론 배제, 실근거만)과 정확히 부합. 채택할 것은 **규칙과 수식**이다.

---

## 1. 라벨링 규칙·수식 (논문별, 정확한 기호)

### Cernera (USENIX Security'23, 최고 권위) — 결정론적, ML 없음
**1-day 러그풀 판정**:
> 유동성 풀이 **정확히 Mint 1회 + Burn 1회**를 emit하고, Burn에서 **mint된 LP토큰의 ≥99% 소각** → 러그풀
> (100% 아닌 이유: 반올림 잔량)

**이익 수식** (Eq.1,2):
```
base_gain = δ_B − fees
net_gain  = base_gain − T_in + T_out − fees_swap    (net_gain > 0 = 성공한 러그)
```
δ_B=투자자 투입 가치토큰, T_in=조작자 인위 추가분(wash), T_out=제거 전 회수분

**임계값**: 1-day token = lifetime<24h · token spammer = 생성 상위 1%(>18개) · sniper bot = 스왑지연 <5블록(BSC)/<3블록(ETH) AND ≥100/≥10개 풀
**결과**: 러그 비율 BSC 81.2% / ETH 86.3%, 이익 ETH $148.93M

### Mazorra (16인용) — 수식 중심
```
HHI = Σ_a B(a)² / (Σ_a B(a))²           # 집중도, 1=독점(위험)
MD  = |(X_l − X_h)/X_h|                  # 최대낙폭 (X_h=고점, X_l=고점후 저점)
RC  = (X_S − X_l)/(X_h − X_l)            # 회복 (X_S=마지막값)
ACC = (1/n)Σ_u c_u,  c_u = 1/(deg(deg−1))·Σ(ŵ_uv·ŵ_vw·ŵ_wu)^(1/3)   # Onnela 가중 군집계수
```
**라벨 3조건 (AND)**: ① 30일 무활동 ② MD≈1 ③ RC≈0
**Uniswap 불변식**: `(x+(1−f)Δx)(y−Δy)=xy`, f=0.003

### From Hype to Collapse (中山대) — 3유형 온체인 규칙, FP 0.26%
**사전 필터**: 최근 24h 평균 거래율 < 5 tx/hour (안정구간 [0.5, 5])
- **Freeze Authority Abuse**: creator가 freeze authority 보유 AND 실제 `FreezeAccount` 명령이 사용자 계정에 ≥1회 실행 (461개)
- **Liquidity Withdrawal**: creator 관련주소(mint authority OR 초기 풀 배포자)가 수익성 유동성 인출 후 활동임계 이하 붕괴 (15,606개)
- **Pump-and-Dump**: 홀더수 AND 풀 토큰잔고 단조감소 AND 홀더 감소율 > **τ_down=0.73** (60,402개)
  - τ_down 도출: 0.50→1.00을 0.01씩 스윕, 0.73까지 안정 → 점진형까지 포함하는 최대값

### MELT (Georgia Tech) — 가격붕괴 + 번들
```
min_price_ratio = (마이그레이션 후 y분 내 최저가) / 마이그레이션 가격,  y=20분
High-risk: min_price_ratio < 0.3  OR  is_manipulated
Low-risk:  min_price_ratio ≥ 0.7  AND  not_manipulated
```
DEX 가격 `p = y/x`, 마이그레이션 = 80% 판매 시

### Catching the Rug (HSE/Skoltech) — 첫 5분 예측
```
MDD_t = (TVL_t − max_{τ≤t}TVL_τ) / max_{τ≤t}TVL_τ        # [−1,0]
Rug_t = 𝟙( (MDD_t < −θ) ∨ (Idle_t > Δt) )                # θ≈0.99, Δt=수명의 80%
```
입력: 첫 5분 거래 → 1시간 내 러그 예측

### SolRPDS (우리 원본, CODASPY'25)
`ADD_TO_REMOVE_RATIO = 총추가유동성 / 총제거유동성` · inactivity = 유동성 제거 후 거래 중단

---

## 2. 🔑 번들/인사이더 추적 알고리즘 (MELT) — 우리 최대 gap 해법

우리 메커니즘 분석에서 "top1≥90%는 69%인데 인사이더 탐지 2.9%뿐"(번들형 못잡음)이 gap이었다. MELT의 **공급 36.5% 조율계정 식별** 방법:

**3개 휴리스틱으로 (계정, 식별자) 튜플 생성 → 병합:**
1. **같은-tx 공동매수**: 한 트랜잭션에서 함께 buy/sell하는 계정들 = 한 주체 (모든 서명키 필요하므로). 식별자 = tx ID. → 공급 9.16%
2. **공통 펀더**: 같은 주소로부터 rent 자금을 받은 계정들 = 같은 소유 (단 **CEX 출금 제외**). 식별자 = 펀더 주소. → 공급 **28.22%** (최대)
3. **Jito 번들**: 같은 Jito bundle ID를 공유한 tx의 계정들 (Jito Explorer 크롤, off-chain). → 공급 15.96%

**병합**: 각 토큰에서 식별자 값이 일치하는 계정을 클러스터 → 겹치는 클러스터 union. **합산 공급 36.50%** (top-10 홀더 지분이 high-risk는 +24%p 상승).

→ 우리가 `getSignaturesForAddress`+`getTransaction`으로 (1)(2)를 구현하면 인사이더 클러스터 탐지 가능 (온체인 사실 기반이라 우리 원칙 부합).

---

## 3. Feature·모델 요약

| 논문 | feature 수 | 핵심 feature | 모델 | 성능 |
|---|---:|---|---|---|
| Cernera | (규칙) | Mint/Burn 이벤트 | 없음 | 러그 86.3%(ETH) |
| Mazorra | 16 | HHI·ACC·MD·RC | XGBoost, FT-Transformer | F1 0.968 |
| From Hype | (규칙) | 6행태통계 | 없음 | FP 0.26% |
| MELT | **122** (맥락6·홀더59·시장22·번들35) | 번들 집중도 | MLP+LSTM | AUPRC 0.583 |
| Catching | 23 | TVL·거래패턴 | XGBoost(fusion) | MCC 0.395 |
| SolRPDS | ~5 | 유동성 add/remove | AdaBoost | ACC 0.976 |

**공통 교훈**: 트리 모델(XGBoost/RF)이 도메인 시프트에서 뉴럴넷·트랜스포머를 일관되게 능가. **시장활동 feature 제거 시 성능 최대 하락**(MELT ablation).

---

## 4. 🔥 결정적 실무 교훈 (논문이 실증)

1. **유동성 lock/burn은 안전신호가 아니다** (Mazorra): Unicrypt로 유동성 잠근 토큰의 **97%가 malicious**. → 우리 풀 검증에서 "LP 잠금"을 안전으로 해석하면 안 됨.
2. **freeze/mint authority 보유만으로 부족** (From Hype): 실제 `FreezeAccount` 명령 실행을 봐야 허니팟 확증.
3. **"market cap"(가상 리저브) ≠ 실제 자본** (Graduation): 온체인 상태는 `complete`·`real_sol_reserves`로 판정.
4. **수명 중앙값 ~14분~1일**: 러그는 즉각적 → 사후 라벨링은 놓치지 않지만 사전 탐지는 첫 5분 데이터 필요.

---

## 5. 우리가 채택할 것 (우선순위)

| # | 기술 | 출처 | 우리 적용 |
|---|---|---|---|
| 1 | **인사이더 번들 클러스터링** (같은-tx + 공통펀더) | MELT | top-holder 우회 케이스 탐지 (우리 gap) |
| 2 | **freeze/withdrawal/pump-dump 3유형 판정** (τ_down=0.73) | From Hype | 풀 검증 유형 세분화 |
| 3 | **Mint1+Burn1+99% 규칙** | Cernera | 하드러그 결정론적 라벨 |
| 4 | **HHI 집중도 + MD/RC 라벨 3조건** | Mazorra | 집중도·낙폭 정량화 |
| 5 | **첫 5분 시계열 feature** | Catching | 실시간 사전탐지 |

모두 **결정론적 온체인 규칙**이라 우리 "실근거만, 휴리스틱 배제" 원칙에 부합한다.

---

*논문: Cernera USENIX Security'23 · Mazorra IACR'22(16인용) · SolRPDS CODASPY'25 · From Hype to Collapse · MELT · Catching the Rug · Graduation. PDF·txt는 `raw/papers/`(gitignore).*
