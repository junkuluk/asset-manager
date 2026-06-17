# 자산관리 앱 재구축 설계서

기존 Streamlit 단일 앱(`application/`)을 **Spring Boot REST 백엔드 + React 프론트엔드**로 분리 재구축한다.
기존 코드는 참고용으로 보존하고, 새 코드는 `backend/`, `frontend/`에 작성한다.

## 1. 결정사항

| 항목 | 선택 |
|------|------|
| 프론트엔드 | React + TypeScript (Vite) |
| 백엔드 | Spring Boot 3 (Java 21, Gradle), 레이어드 + 약간의 포트 |
| 인증 | 단일 사용자 (간단 로그인) |
| 엑셀 파싱 | 백엔드 (Apache POI) |
| DB | PostgreSQL |

## 2. 핵심 간소화 (기존 대비)

기존 구조가 과하게 복잡했던 부분을 다음과 같이 정리한다.

1. **거래 테이블 통합** — `transaction` + `card_transaction` + `bank_transaction` 3개 테이블을
   단일 `transaction` 테이블로 통합. 카드/은행 전용 필드는 nullable 컬럼으로 보관.
2. **잔액 이력 테이블 제거** — `account_balance_history`(누적잔액 추적)를 제거.
   잔액은 `initial_balance + SUM(거래)`로 그때그때 계산. 동기화 버그 원천 차단.
3. **거래처(transaction_party) 제거** — 항상 기본값 1로만 쓰이던 미사용 개념. `merchant` 텍스트로 대체.
4. **카테고리 단순화** — `materialized_path_desc` + `depth` + `category_code` 3중 관리를 제거하고
   `parent_id`만 유지. 계층 경로는 서비스에서 계산. 최대 2단계(대분류/소분류) 권장.
5. **규칙엔진 통합** — `rule`/`rule_condition` 과 `transfer_rule`/`transfer_rule_condition`(거의 동일 로직)을
   단일 `rule`/`rule_condition`로 통합하고 `action`(CATEGORIZE / TRANSFER)으로 구분.
6. **중복/실험 페이지 제거** — `2_월별손익` 2종, `7_*` 3종, `seeder copy.py`, 디버깅 페이지 등 정리.

## 3. 새 데이터 모델 (Flyway V1)

```
account            계좌/카드
  id, name, type(BANK|CARD|INVEST|CASH), is_asset, initial_balance, created_at

category           수입/지출 분류 (계층)
  id, name, type(INCOME|EXPENSE), parent_id, sort_order

transaction        모든 거래 (카드/은행/수기 통합)
  id, account_id, type(INCOME|EXPENSE|TRANSFER|INVEST), source(CARD|BANK|MANUAL),
  category_id, linked_account_id, txn_date, amount(BIGINT, 양수), content, memo, merchant,
  is_manual_category, dedup_hash(UNIQUE), 
  card_approval_no, card_name, card_kind   -- 카드 전용(nullable)
  bank_branch                              -- 은행 전용(nullable)

rule               자동 분류/이체 규칙
  id, name, priority, action(CATEGORIZE|TRANSFER), category_id, linked_account_id

rule_condition     규칙 조건 (AND 결합)
  id, rule_id, field, match_type(CONTAINS|EXACT|REGEX|GT|LT|EQ), value
```

`dedup_hash` = source별 자연키 해시(카드: provider+승인번호 / 은행: 날짜+시간+입출금액).
중복 업로드 시 이 해시로 스킵.

## 4. 백엔드 패키지 구조 (레이어드 + 포트)

```
com.assetmanager
├─ AssetManagerApplication
├─ common/            공통(설정, 예외, 응답)
├─ domain/            JPA 엔티티 + enum (Account, Category, Transaction, Rule, RuleCondition)
├─ port/             out 포트 인터페이스 (ExcelParser 등 교체 가능한 지점만)
├─ application/       서비스(유스케이스): TransactionService, ImportService, RuleEngine, AccountService, CategoryService, DashboardService
├─ adapter/
│  ├─ in/web/         REST 컨트롤러 + DTO
│  └─ out/excel/      POI 파서 (ShinhanCard, KookminCard, ShinhanBank)
└─ repository/        Spring Data JPA 리포지토리
```

## 5. REST API (초안)

```
POST   /api/imports/card      multipart 파일 → {inserted, skipped}
POST   /api/imports/bank      multipart 파일 → {inserted, skipped}
GET    /api/transactions      ?from&to&type&source  (목록)
PATCH  /api/transactions/{id} 카테고리/메모/이체 재분류
GET    /api/accounts          계좌+계산된 잔액
POST   /api/accounts
GET    /api/categories        계층 트리
POST   /api/categories
GET    /api/rules /  POST/PUT/DELETE
GET    /api/dashboard/monthly         월별 수입/지출/투자
GET    /api/dashboard/category-summary ?type&from&to
GET    /api/dashboard/assets          월별 자산추이
```

## 6. 진행 순서

1. [x] 설계서
2. [x] 백엔드 골격: Gradle(wrapper), application.yml, Flyway 스키마, 도메인 엔티티, 리포지토리
3. [x] 서비스: RuleEngine, ImportService, 엑셀 파서(POI 3종), Account/Transaction/Category/Dashboard 서비스
4. [x] REST 컨트롤러 + DTO + 단일사용자 인증 + DataSeeder  → `./gradlew compileJava` 성공
5. [x] React 프론트(Vite + TS): API 클라이언트, 로그인/업로드/거래목록/대시보드/계좌 → `npm run build` 성공

### 검증 상태
- 백엔드: `compileJava` 통과(컴파일 OK). **실제 기동(bootRun)은 PostgreSQL 필요 — 미실행.**
- 프론트: `tsc --noEmit` + `vite build` 통과.

### 남은 개선(선택)
- 규칙 관리 UI/API(CRUD) — 현재는 시드 + DB로만 관리
- 거래 재분류 UI 버튼(백엔드 API는 존재)
- 카테고리별 지출 차트(category-summary API는 존재) 화면
- 실제 엑셀 샘플(.streamlit/*.xls)로 파서 통합 테스트
- 통합테스트(Testcontainers PostgreSQL)
