<div align="center">
<img src="../assets/lena_serious.gif" width="360" alt="Lena" />
</div>

# 🔷 Ethereum 스캠 주소

전량 **Etherscan `getaddresstag`로 검증**하고, 미검증분은 **GoPlus로 2차 검증**해 등급(tier)을 매긴 데이터.

## 파일

| 파일 | 개수 | 용도 |
|---|---:|---|
| **`master_ethereum_confirmed.csv`** | 23,943 | 🥇 **차단/스크리닝용 (권장)** — 아래 3개 확정 등급만 |
| `master_ethereum_etherscan_confirmed.csv` | 21,796 | 🔒 최엄격 — Etherscan 공식 악성만 |
| `master_ethereum_verified.csv` | 219,570 | 🔍 전체 감사본 (모든 주소 + tier 컬럼) |
| `archive_ethereum_community_unverified.csv` | ~192,900 | 📦 미검증 신고 (참고용 — 무고 주소 혼입 가능) |
| `master_ethereum.csv` | 217,411 | 교차출처 병합 원본 (검증 컬럼 없음, 파이프라인 중간산출) |
| `verify/` | — | 검증 캐시 (Etherscan·GoPlus 응답) |

## 등급(tier) 가이드

| 등급 | 근거 | 신뢰도 |
|---|---|---|
| `CONFIRMED_MALICIOUS` | Etherscan 공식 악성 라벨 (reputation 2/3) | 🟢 최고 |
| `GOPLUS_CONFIRMED` | GoPlus 독립 악성 라벨 (phishing·stealing·blackmail·cybercrime·sanctioned) | 🟢 높음 |
| `CROSS_CONFIRMED` | 2개+ 독립 소스 교차확인 (자금추적 소스 제외 기준) | 🟡 높음 |
| `COMMUNITY_ONLY` | 커뮤니티 신고 1건, 미검증 | 🟠 참고용 |
| `EXCHANGE_FALSE_POSITIVE` | 거래소·정상 서비스로 판명 | 🔴 사용 금지 |

## 스키마

| 컬럼 | 설명 |
|---|---|
| `address` | 지갑/컨트랙트 주소 (0x, 소문자) |
| `source_count` | 등장한 독립 소스 수 |
| `sources` | 소스 목록 (`\|` 구분) — [sources/README.md](../sources/README.md) 참고 |
| `categories` | 스캠 유형 (phishing, exploit, sanctions, enforcement_frozen …) |
| `etherscan_reputation` | 2/3 = 공식 악성 |
| `etherscan_labels` | Phish/Hack, Exploit, Poisoning, Heist … |
| `etherscan_nametag` | 예: `Fake_Phishing371`, `Ronin Bridge Exploiter` |
| `tier` | 위 등급 가이드 참고 |

## 주요 구성

- Etherscan 공식 악성 상위: **Phish/Hack 18,132+** · Poisoning 1,234 · Upbit Hack 815 · Exploit 607 · Heist 133 · Bybit Exploit 63
- **USDT/USDC 발행사 동결 3,335**: Tether `AddedBlackList` · Circle `Blacklisted` 온체인 이벤트 전수 스캔 (해제분 상쇄, 현재 동결 중만)
- 북한 DPRK 수사 데이터(tayvano)는 `TAINTED_TRACE` 처리 — 독립 검증 없이는 confirmed 진입 불가

## 한계

- `COMMUNITY_ONLY` 아카이브는 피해자 신고 원문 기반이라 드물게 피해자·거래소 주소가 섞일 수 있음 → confirmed만 차단 리스트로 사용 권장
- GoPlus 2차 검증이 아카이브를 순차 처리 중 → confirmed는 매일 증가
