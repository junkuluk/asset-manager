package com.assetmanager.adapter.in.web;

import com.assetmanager.adapter.in.web.dto.AccountResponse;
import com.assetmanager.adapter.in.web.dto.CreateAccountRequest;
import com.assetmanager.application.AccountService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/accounts")
@RequiredArgsConstructor
public class AccountController {

    private final AccountService accountService;

    @GetMapping
    public List<AccountResponse> list() {
        return accountService.listWithBalance().stream().map(AccountResponse::from).toList();
    }

    @PostMapping
    public AccountResponse create(@Valid @RequestBody CreateAccountRequest req) {
        var account = accountService.create(req.name(), req.type(), req.asset(), req.initialBalance());
        return new AccountResponse(account.getId(), account.getName(), account.getType(),
                account.isAsset(), account.getInitialBalance(), account.getInitialBalance());
    }
}
