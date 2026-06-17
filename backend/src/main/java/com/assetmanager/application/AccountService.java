package com.assetmanager.application;

import com.assetmanager.domain.Account;
import com.assetmanager.domain.AccountType;
import com.assetmanager.repository.AccountRepository;
import com.assetmanager.repository.TransactionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class AccountService {

    private final AccountRepository accountRepository;
    private final TransactionRepository transactionRepository;

    /** 계좌 + 계산된 현재 잔액. */
    public record AccountView(Account account, long balance) {}

    @Transactional(readOnly = true)
    public List<AccountView> listWithBalance() {
        return accountRepository.findAll().stream()
                .map(a -> new AccountView(a, balanceOf(a)))
                .toList();
    }

    /** 잔액 = 초기잔액 + 자기거래 순합 + 이체/투자 유입. (이력 테이블 없이 매번 계산) */
    @Transactional(readOnly = true)
    public long balanceOf(Account a) {
        return a.getInitialBalance()
                + transactionRepository.ownNet(a.getId())
                + transactionRepository.incoming(a.getId());
    }

    @Transactional
    public Account create(String name, AccountType type, boolean asset, long initialBalance) {
        return accountRepository.save(new Account(name, type, asset, initialBalance));
    }
}
