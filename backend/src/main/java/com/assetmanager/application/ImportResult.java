package com.assetmanager.application;

/** 엑셀 업로드 결과 요약. */
public record ImportResult(int inserted, int skipped) {}
