package com.assetmanager.common.auth;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 단일 사용자 토큰 인증. 설정된 자격증명과 일치하면 인메모리 토큰을 발급한다.
 * (개인용 로컬 앱 수준의 간단 인증 — 외부 공개 시 강화 필요)
 */
@Service
public class AuthService {

    private final String username;
    private final String password;
    private final Set<String> validTokens = ConcurrentHashMap.newKeySet();

    public AuthService(@Value("${app.auth.username}") String username,
                       @Value("${app.auth.password}") String password) {
        this.username = username;
        this.password = password;
    }

    public String login(String user, String pass) {
        if (!username.equals(user) || !password.equals(pass)) {
            throw new IllegalArgumentException("아이디 또는 비밀번호가 올바르지 않습니다.");
        }
        String token = UUID.randomUUID().toString();
        validTokens.add(token);
        return token;
    }

    public boolean isValid(String token) {
        return token != null && validTokens.contains(token);
    }

    public void logout(String token) {
        validTokens.remove(token);
    }
}
