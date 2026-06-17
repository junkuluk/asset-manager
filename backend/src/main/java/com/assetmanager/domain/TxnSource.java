package com.assetmanager.domain;

/** 거래 출처(어디서 들어온 데이터인지). */
public enum TxnSource {
    CARD,    // 카드사 엑셀
    BANK,    // 은행 엑셀
    MANUAL   // 수기 입력
}
