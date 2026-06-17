package com.assetmanager.common;

/** 요청한 리소스가 없을 때. 핸들러에서 404로 변환. */
public class NotFoundException extends RuntimeException {
    public NotFoundException(String message) {
        super(message);
    }
}
