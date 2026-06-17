package com.assetmanager.adapter.in.web.dto;

import com.assetmanager.application.TransactionService.TransactionView;
import com.assetmanager.domain.Transaction;
import com.assetmanager.domain.TxnSource;
import com.assetmanager.domain.TxnType;

import java.time.OffsetDateTime;

public record TransactionResponse(
        Long id,
        OffsetDateTime txnDate,
        TxnType type,
        TxnSource source,
        long amount,
        String content,
        String memo,
        String merchant,
        Long accountId,
        String accountName,
        Long categoryId,
        String categoryName,
        Long linkedAccountId,
        boolean manualCategory,
        String cardName
) {
    public static TransactionResponse from(TransactionView v) {
        Transaction t = v.txn();
        return new TransactionResponse(
                t.getId(), t.getTxnDate(), t.getType(), t.getSource(), t.getAmount(),
                t.getContent(), t.getMemo(), t.getMerchant(),
                t.getAccountId(), v.accountName(),
                t.getCategoryId(), v.categoryName(),
                t.getLinkedAccountId(), t.isManualCategory(), t.getCardName());
    }
}
