package com.assetmanager.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "rule_condition")
@Getter
@Setter
@NoArgsConstructor
public class RuleCondition {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "rule_id", nullable = false)
    private Long ruleId;

    /** 검사할 거래 필드명: content | merchant | amount. */
    @Column(nullable = false)
    private String field;

    @Enumerated(EnumType.STRING)
    @Column(name = "match_type", nullable = false)
    private MatchType matchType;

    @Column(nullable = false)
    private String value;
}
