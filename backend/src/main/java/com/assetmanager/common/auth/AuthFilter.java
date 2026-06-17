package com.assetmanager.common.auth;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/** /api/** 요청에 유효한 Bearer 토큰을 요구. 로그인/프리플라이트는 통과. */
@Component
@Order(1)
@RequiredArgsConstructor
public class AuthFilter extends OncePerRequestFilter {

    private final AuthService authService;

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        String path = req.getRequestURI();
        boolean isApi = path.startsWith("/api/");
        boolean isLogin = path.equals("/api/auth/login");
        boolean isPreflight = "OPTIONS".equalsIgnoreCase(req.getMethod());

        if (!isApi || isLogin || isPreflight) {
            chain.doFilter(req, res);
            return;
        }

        String auth = req.getHeader("Authorization");
        String token = auth != null && auth.startsWith("Bearer ") ? auth.substring(7) : null;
        if (!authService.isValid(token)) {
            res.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            res.setContentType("application/json;charset=UTF-8");
            res.getWriter().write("{\"error\":\"인증이 필요합니다.\"}");
            return;
        }
        chain.doFilter(req, res);
    }
}
