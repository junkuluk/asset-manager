package com.assetmanager.adapter.in.web.dto;

import jakarta.validation.constraints.NotNull;

/** 지출 거래를 이체/투자로 재분류할 때 연결할 계좌. */
public record ReclassifyRequest(@NotNull Long linkedAccountId) {}
