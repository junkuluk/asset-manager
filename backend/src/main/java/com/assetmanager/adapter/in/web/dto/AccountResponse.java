package com.assetmanager.adapter.in.web.dto;

import com.assetmanager.application.AccountService.AccountView;
import com.assetmanager.domain.AccountType;

public record AccountResponse(
        Long id,
        String name,
        AccountType type,
        boolean asset,
        long initialBalance,
        long balance
) {
    public static AccountResponse from(AccountView v) {
        return new AccountResponse(
                v.account().getId(), v.account().getName(), v.account().getType(),
                v.account().isAsset(), v.account().getInitialBalance(), v.balance());
    }
}
