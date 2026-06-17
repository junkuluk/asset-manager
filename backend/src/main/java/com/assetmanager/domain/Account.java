package com.assetmanager.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.OffsetDateTime;

@Entity
@Table(name = "account")
@Getter
@Setter
@NoArgsConstructor
public class Account {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AccountType type;

    /** 자산 계좌(true) / 부채·카드(false). 순자산 계산에 사용. */
    @Column(name = "is_asset", nullable = false)
    private boolean asset = true;

    /** 거래 이전의 기준 잔액. 현재 잔액 = initialBalance + 거래 합산(서비스에서 계산). */
    @Column(name = "initial_balance", nullable = false)
    private long initialBalance = 0;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt = OffsetDateTime.now();

    public Account(String name, AccountType type, boolean asset, long initialBalance) {
        this.name = name;
        this.type = type;
        this.asset = asset;
        this.initialBalance = initialBalance;
    }
}
