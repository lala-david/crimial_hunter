<div align="center">

# 🎯 Criminal Hunter

<img src="assets/lena.gif" width="440" alt="Lena (86: Eighty-Six)" />

### 크립토 스캠 주소 데이터셋 — Solana + Ethereum

![Chains](https://img.shields.io/badge/chains-Solana%20%7C%20Ethereum-9945FF?style=flat-square)
![Verified](https://img.shields.io/badge/verified%20wallets-36K%2B-success?style=flat-square)
![Total](https://img.shields.io/badge/total%20addresses-330K%2B-blue?style=flat-square)
![Update](https://img.shields.io/badge/auto%20update-daily-orange?style=flat-square)

피싱 · 드레이너 · 러그풀 · 해킹 · 제재 지갑 주소를 공개 소스에서 수집하고
**온체인 + Etherscan + GoPlus**로 검증한 데이터셋.
휴리스틱(그래프 크롤·통계 추정·ML) 없이 **실제 근거만**.

</div>

---

## 📌 한눈에 보기

| | 개수 | 파일 |
|---|---:|---|
| 🟣 **솔라나 스캠 지갑** | **13,079** | [`solana/master_solana_wallets.csv`](solana/) |
| 🔷 **이더리움 확정 스캠** | **23,086** | [`ethereum/master_ethereum_confirmed.csv`](ethereum/) |
| 🪙 솔라나 스캠 토큰/풀 (분리) | 101,547 | [`solana/master_solana_tokens.csv`](solana/) |
| 🔍 이더리움 전체 감사본 | 217,411 | [`ethereum/master_ethereum_verified.csv`](ethereum/) |

> 매일 자동 갱신 — 최신 수치는 [`MANIFEST.json`](MANIFEST.json)

## 🗂️ 구조

```
├── ethereum/   🔷 이더리움 데이터 + 등급 가이드     → ethereum/README.md
├── solana/     🟣 솔라나 데이터 + 온체인 분류       → solana/README.md
├── sources/    📡 소스별 원천 데이터 (25+ 소스)     → sources/README.md
└── scripts/    ⚙️ 수집·검증 파이프라인 + 방법론     → scripts/README.md
```

각 폴더의 README에 데이터 설명 · 스키마 · 사용 가이드가 있습니다.

## ⚠️ 이용 안내

- 연구·방어(차단/스크리닝) 목적. **등급(tier)을 확인하고 쓰세요** — `CONFIRMED_*`만 고신뢰.
- 원본 소스별 라이선스 상이 → 상업적 이용 전 확인 ([sources/README.md](sources/README.md)).
- 잘못 포함된 주소는 [Issue](../../issues)로 제보 — 근거 확인 후 제거합니다.

---

<div align="center">
<img src="assets/lena_field.gif" width="440" alt="Lena" />
</div>
