package com.assetmanager.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.OffsetDateTime;

/**
 * 모든 거래의 단일 테이블. 카드/은행/수기 거래를 source로 구분하고
 * 출처 전용 필드는 nullable 컬럼으로 보관한다(기존 card/bank 서브테이블 통합).
 */
@Entity
@Table(name = "transaction")
@Getter
@Setter
@NoArgsConstructor
public class Transaction {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id", nullable = false)
    private Long accountId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private TxnType type;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private TxnSource source;

    @Column(name = "category_id")
    private Long categoryId;

    /** 이체/투자 시 상대 계좌. */
    @Column(name = "linked_account_id")
    private Long linkedAccountId;

    @Column(name = "txn_date", nullable = false)
    private OffsetDateTime txnDate;

    /** 항상 양수. 부호는 type으로 판단. */
    @Column(nullable = false)
    private long amount;

    private String content;
    private String memo;
    private String merchant;

    /** 사용자가 수동으로 카테고리를 지정했으면 규칙 재적용에서 제외. */
    @Column(name = "is_manual_category", nullable = false)
    private boolean manualCategory = false;

    /** 중복 업로드 방지용 자연키 해시(UNIQUE). */
    @Column(name = "dedup_hash", nullable = false, unique = true)
    private String dedupHash;

    // 카드 전용
    @Column(name = "card_approval_no")
    private String cardApprovalNo;
    @Column(name = "card_name")
    private String cardName;
    @Column(name = "card_kind")
    private String cardKind;

    // 은행 전용
    @Column(name = "bank_branch")
    private String bankBranch;
}
