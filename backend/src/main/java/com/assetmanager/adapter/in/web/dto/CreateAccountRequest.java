package com.assetmanager.adapter.in.web.dto;

import com.assetmanager.domain.AccountType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record CreateAccountRequest(
        @NotBlank String name,
        @NotNull AccountType type,
        boolean asset,
        long initialBalance
) {}
