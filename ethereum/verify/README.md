<div align="center">
<img src="../../assets/lena_night.gif" width="360" alt="Lena" />
</div>

# 🔎 Ethereum 검증 캐시

이더리움 주소를 외부 API로 검증한 원본 응답 캐시. [`build_eth_verified.py`](../../scripts/build_eth_verified.py)가
이 파일들을 읽어 등급(tier)을 매긴다. **이어받기용 캐시라 삭제하면 전량 재조회가 필요하니 주의.**

## 파일

| 파일 | 내용 | 스키마 |
|---|---|---|
| `etherscan_verify.csv` | Etherscan `getaddresstag` 전량 조회 결과 (21만+) | `address, reputation, labels, nametag` |
| `goplus_verify.csv` | GoPlus `address_security` 2차 검증 결과 (진행 중 — 매일 증가) | `address, flags` |

## 해석

- `reputation` — `2`/`3` = Etherscan 공식 악성 → `CONFIRMED_MALICIOUS`
- `flags` — `\|` 구분 GoPlus 플래그. 강한 플래그(phishing_activities · stealing_attack ·
  blackmail_activities · cybercrime · sanctioned)만 `GOPLUS_CONFIRMED`로 채택.
  `blacklist_doubt`(의심) · `honeypot_related`(연관성) · `mixer`는 **불채택**.
- 빈 값 = 해당 API에 아무 정보 없음 (악성 아니라는 뜻이 아님)

## 갱신

- Etherscan: 매일 자동 갱신 때 마스터의 **신규 주소만** 델타 조회 (`ETHERSCAN_KEY` 필요)
- GoPlus: 일 4,000개 슬라이스 + 별도 대량 배치, 락파일로 동시 실행 방지 (키 불필요)
