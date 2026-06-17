package com.assetmanager.domain;

/** 규칙이 매칭됐을 때 수행할 동작. */
public enum RuleAction {
    CATEGORIZE,  // category_id 부여
    TRANSFER     // 이체로 표시하고 linked_account 연결
}
