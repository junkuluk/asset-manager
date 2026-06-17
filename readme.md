# 자산관리 (Asset Manager) — 재구축판

카드사·은행 엑셀을 올려 가계부/실사용 내역을 정리하는 개인용 앱.
기존 Streamlit 단일 앱을 **Spring Boot REST 백엔드 + React 프론트엔드**로 분리 재구축했다.
설계·간소화 내역은 [REBUILD.md](REBUILD.md) 참고. (기존 코드는 `application/`에 보존)

## 구성

```
backend/    Spring Boot 3 (Java 21, Gradle) — REST API + 엑셀 파싱(POI) + 규칙엔진
frontend/   React + TypeScript (Vite) — 대시보드/거래내역/업로드/계좌
application/ (구) Streamlit 앱 — 참고용 보존
```

## 사전 준비

- JDK 21, Node 20+
- PostgreSQL DB 하나 (예: `asset_manager`)

## 백엔드 실행

```bash
cd backend
# DB 접속/계정 환경변수 (기본값: localhost:5432/asset_manager, postgres/postgres)
export DB_URL=jdbc:postgresql://localhost:5432/asset_manager
export DB_USER=postgres
export DB_PASSWORD=postgres
# 로그인 계정 (기본 admin / admin1234)
export APP_USER=admin
export APP_PASSWORD=admin1234

./gradlew bootRun
```

- 최초 기동 시 Flyway가 스키마를 생성하고, `DataSeeder`가 기본 계좌·카테고리·규칙을 시드한다.
- API는 `http://localhost:8080/api/...`

## 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (api는 8080으로 프록시)
```

브라우저에서 `http://localhost:5173` → 로그인(admin / admin1234) → 업로드 메뉴에서 엑셀 업로드.

## 엑셀 인식 규칙

파일명으로 출처를 판별한다.
- `Shinhancard_*.xls` → 신한카드
- `kookmin_*.xls` / 파일명에 `국민` → 국민카드
- `*은행*` / `*거래내역*` → 신한은행

## 주요 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/auth/login` | 로그인 → 토큰 |
| POST | `/api/imports` | 엑셀 업로드(multipart `file`) |
| GET | `/api/transactions?from&to&type&source` | 거래 목록 |
| PATCH | `/api/transactions/{id}` | 카테고리/메모 수정 |
| POST | `/api/transactions/{id}/reclassify` | 지출→이체/투자 재분류 |
| GET | `/api/accounts` | 계좌 + 계산된 잔액 |
| GET | `/api/categories` | 카테고리(경로 포함) |
| GET | `/api/dashboard/monthly` | 월별 수입/지출/투자 |
| GET | `/api/dashboard/category-summary?type&from&to` | 카테고리별 합계 |
