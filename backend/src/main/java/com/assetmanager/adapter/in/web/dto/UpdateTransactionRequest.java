package com.assetmanager.adapter.in.web.dto;

/** 카테고리/메모 부분 수정. null 필드는 변경하지 않음. */
public record UpdateTransactionRequest(Long categoryId, String memo) {}
