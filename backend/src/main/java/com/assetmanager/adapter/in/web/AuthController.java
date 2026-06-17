package com.assetmanager.adapter.in.web;

import com.assetmanager.common.auth.AuthService;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    public record LoginRequest(@NotBlank String username, @NotBlank String password) {}

    @PostMapping("/login")
    public Map<String, String> login(@RequestBody LoginRequest req) {
        return Map.of("token", authService.login(req.username(), req.password()));
    }

    @PostMapping("/logout")
    public void logout(@RequestHeader(value = "Authorization", required = false) String auth) {
        if (auth != null && auth.startsWith("Bearer ")) {
            authService.logout(auth.substring(7));
        }
    }
}
