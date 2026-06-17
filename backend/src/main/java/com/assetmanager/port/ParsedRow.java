package com.assetmanager.port;

import java.time.OffsetDateTime;

/**
 * 카드사/은행 엑셀에서 파싱한 한 행의 표준화된 표현(출처 무관).
 * 이후 ImportService가 규칙엔진/계좌 매핑을 거쳐 Transaction으로 변환한다.
 */
public record ParsedRow(
        OffsetDateTime date,
        long amount,          // 양수 절대값
        boolean income,       // 은행: 입금이면 true. 카드는 항상 false(지출).
        String content,       // 가맹점/내용
        String merchant,      // 상대/적요 등 부가
        // 카드 전용
        String cardApprovalNo,
        String cardName,
        String cardKind,      // 신용 | 체크
        // 은행 전용
        String bankBranch,
        // 중복 판별용 자연키(출처별 규칙으로 파서가 채움)
        String naturalKey
) {
    public static ParsedRow card(OffsetDateTime date, long amount, String content,
                                 String approvalNo, String cardName, String cardKind,
                                 String naturalKey) {
        return new ParsedRow(date, amount, false, content, null,
                approvalNo, cardName, cardKind, null, naturalKey);
    }

    public static ParsedRow bank(OffsetDateTime date, long amount, boolean income,
                                 String content, String merchant, String branch,
                                 String naturalKey) {
        return new ParsedRow(date, amount, income, content, merchant,
                null, null, null, branch, naturalKey);
    }
}
