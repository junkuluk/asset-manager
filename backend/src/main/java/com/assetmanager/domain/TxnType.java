package com.assetmanager.domain;

/** 거래 방향/성격. */
public enum TxnType {
    INCOME,    // 수입
    EXPENSE,   // 지출
    TRANSFER,  // 내부 이체(자산 간 이동, 손익에 미포함)
    INVEST     // 투자 납입
}
