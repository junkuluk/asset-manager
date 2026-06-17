package com.assetmanager.port;

import com.assetmanager.domain.TxnSource;

import java.io.InputStream;
import java.util.List;

/**
 * 출처별 엑셀 명세서 파서의 out 포트.
 * 신한카드/국민카드/신한은행 등 구현체를 교체·추가할 수 있다.
 */
public interface StatementParser {

    /** 이 파서가 처리하는 출처(CARD/BANK). */
    TxnSource source();

    /** 파일명/내용으로 이 파서가 처리 가능한지 판별. */
    boolean supports(String filename);

    /** 엑셀 스트림을 표준 행 목록으로 파싱. */
    List<ParsedRow> parse(InputStream in);

    /** 거래가 귀속될 계좌 이름(예: "신한카드"). */
    String accountName(ParsedRow row);
}
