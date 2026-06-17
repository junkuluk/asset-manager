package com.assetmanager.domain;

/** 카테고리 성격. 수입/지출만 분류 대상으로 둔다(이체/투자는 거래 type으로 구분). */
public enum CategoryType {
    INCOME,
    EXPENSE
}
