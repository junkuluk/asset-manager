package com.assetmanager.domain;

/** 계좌 종류. */
public enum AccountType {
    BANK,    // 은행 입출금 계좌
    CARD,    // 신용/체크 카드
    INVEST,  // 투자(주식/코인/저축 등) 계좌
    CASH     // 현금
}
