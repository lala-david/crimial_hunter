<div align="center">
<img src="../assets/lena_smile.gif" width="340" alt="Lena" />
</div>

# 🔬 러그풀 조기 감지 연구

우리 스캠 토큰 데이터셋으로 "러그풀에 공통된 온체인 특징이 있는가, 그것으로 조기 감지가 되는가"를 실측한 연구.

**핵심 결론:** 단일 지표(홀더 집중도) 하나가 오탐 3.4%로 러그의 69%를 잡는다. 단, 초기 실험(러그=RugCheck/정상=Jupiter)은 **라벨 약함·출처편향**이 있었고(`code/audit.py`가 진단), 이를 **온체인 검증 데이터셋 SolRPDS**로 바로잡은 정직한 성능은 **MCC 0.55 / AUC 0.90** (→ [`docs/ML_SOLRPDS_RESULTS.md`](docs/ML_SOLRPDS_RESULTS.md)).

---

## 📁 폴더 구조

이 폴더는 코드·데이터·문서·그림으로 정리돼 있다. **코드는 코드끼리, 데이터는 데이터끼리.**

| 폴더 | 내용 |
|---|---|
| [`code/`](code/) | 모든 파이썬 스크립트 — 수집(`collect_*`, `scan_all_sol`, `verify_pools`)과 분석(`analyze_*`, `compare`, `audit`, `ml_*`, `finalize_pools`) |
| [`data/`](data/) | 모든 `.csv` feature 파일과 `.txt` mint 목록 |
| [`figures/`](figures/) | 시각화 `.png` (PCA/t-SNE) |
| [`docs/`](docs/) | 심화 분석 문서 `.md` |

스크립트의 상대경로는 이 구조에 맞게 이미 수정됨: 데이터는 `../data/`, 그림은 `../figures/`, 저장소 루트(`solana/` 등)는 `../../` 로 참조.

## 📄 문서 (`docs/`)

| 문서 | 요약 |
|---|---|
| **[ML_SOLRPDS_RESULTS.md](docs/ML_SOLRPDS_RESULTS.md)** | **제대로 된 실험** — SolRPDS(온체인 검증 라벨·동일집단)로 두 문제 해결, 현실 성능 MCC 0.55, 논문 0.94의 타임스탬프 누수 지적, 스케일링 필수 입증 |
| [POOL_VERIFICATION.md](docs/POOL_VERIFICATION.md) | 유동성 풀 주소 검증 방법 — 러그완료/오탐/활성 판정과 스캠코인 mint 역추출 |
| [RESEARCH_COMPARISON.md](docs/RESEARCH_COMPARISON.md) | 선행 연구 대비 우리 결과 비교 |
| [RUGPULL_MECHANISM.md](docs/RUGPULL_MECHANISM.md) | 러그풀 5유형과 온체인 발생 메커니즘, 탐지에 필요한 온체인 데이터 TOP 10 |
| [RUGPULL_TECHNIQUES.md](docs/RUGPULL_TECHNIQUES.md) | 러그 수법 상세 — 무한발행/허니팟/선보유 덤프/유동성 인출/인사이더 번들 |

## 📊 주요 데이터 (`data/`)

| 파일 | 설명 |
|---|---|
| `token_features.csv` | 러그(양성) 1,500개 온체인 특징 (RugCheck report 기반) |
| `control_features.csv` | 정상(음성) 350개 대조군 특징 |
| `dex_features.csv` | DexScreener 거래패턴 feature (RPC 우회) |
| `sol_onchain_scan.csv` | 솔라나 토큰 전량 온체인 스캔 (계정유형/권한/확장) |
| `pool_verdict.csv` | 풀 주소 검증 판정 결과 |
| `mechanism_features.csv` | 메커니즘 분류용 확장 feature |
| `*_mints.txt` | mint 주소 목록 — `rug_mints`, `legit_mints`, `control_mints`, `sample_mints`, `mechanism_mints`, `scam_mints_from_pools`, `false_positive_pools` |

## ▶️ 재현

```bash
# 수집 (네트워크)
python research/code/collect_features.py <mint목록.txt> research/data/token_features.csv 1500   # 러그
python research/code/collect_features.py <정상목록.txt> research/data/control_features.csv 350   # 대조군

# 분석 (로컬)
python research/code/analyze_features.py     # 러그 단독 프로파일
python research/code/compare.py              # 러그 vs 정상 판별력
python research/code/ml_proper.py            # 모델 비교(교정본)
python research/code/analyze_categories.py   # 온체인 카테고리 분류
```

## 결과 요약 — 판별력 있는 신호

| 룰 (이 조건이면 러그 의심) | 러그 검출 | 정상 오탐 |
|---|---:|---:|
| 단일홀더 지분 ≥ 99% | 30.2% | **0.3%** |
| 단일홀더 지분 ≥ 95% | 50.4% | **1.1%** |
| **단일홀더 지분 ≥ 90%** | **69.1%** | **3.4%** |
| **복합: 단일홀더 ≥90% AND 유동성 ≤$100** | 22.9% | **0.6%** |

- **러그의 본질은 "물량 독점"** — 최대 단일 홀더 90%+ 가 러그의 69%, 정상은 3.4%뿐.
- **권한 남용(무한발행·동결)은 요즘 거의 안 씀** — pump.fun 등이 권한 자동 소각 → "선보유 후 덤프"가 절대다수.
- **임계값이 판별력의 전부** — 느슨하게(상위10홀더 80%) 잡으면 정상의 42%가 오탐.

## 한계

1. **생존 편향**: 러그 샘플은 RugCheck가 인식한 "살아있는" 토큰 (완료돼 계정 닫힌 러그는 별도 분석 필요).
2. **인사이더 우회**: 여러 지갑에 쪼갠 물량은 지갑 클러스터링 필요 — `insiders_detected` 신호 약함.
3. **표본**: 러그 1,500 / 정상 350 (출처 편향 존재, `audit.py`·`ml_proper.py`에서 정직하게 진단).
