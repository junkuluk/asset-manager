package com.assetmanager.domain;

/** 규칙 조건의 비교 방식. */
public enum MatchType {
    CONTAINS,  // 문자열 포함
    EXACT,     // 정확히 일치(trim 후)
    REGEX,     // 정규식(대소문자 무시)
    GT,        // 숫자 >
    LT,        // 숫자 <
    EQ         // 숫자 ==
}
