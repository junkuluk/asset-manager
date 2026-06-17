package com.assetmanager.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * 자동 분류/이체 규칙. 기존 rule + transfer_rule 두 체계를 action으로 통합.
 * 조건(RuleCondition)은 rule_id로 별도 조회하며, 모두 AND로 만족될 때 적용된다.
 */
@Entity
@Table(name = "rule")
@Getter
@Setter
@NoArgsConstructor
public class Rule {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private int priority = 0;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private RuleAction action;

    /** action=CATEGORIZE 일 때 부여할 카테고리. */
    @Column(name = "category_id")
    private Long categoryId;

    /** action=TRANSFER 일 때 연결할 상대 계좌. */
    @Column(name = "linked_account_id")
    private Long linkedAccountId;
}
