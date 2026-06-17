package com.assetmanager.repository;

import com.assetmanager.domain.Transaction;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Set;

public interface TransactionRepository extends JpaRepository<Transaction, Long> {

    boolean existsByDedupHash(String dedupHash);

    @Query("select t.dedupHash from Transaction t where t.dedupHash in :hashes")
    Set<String> findExistingHashes(@Param("hashes") Set<String> hashes);

    @Query("""
            select t from Transaction t
            where t.txnDate >= :from and t.txnDate < :to
            order by t.txnDate desc
            """)
    List<Transaction> findInRange(@Param("from") OffsetDateTime from,
                                  @Param("to") OffsetDateTime to);

    List<Transaction> findByCategoryIdAndManualCategoryFalse(Long categoryId);

    /** 계좌 자신의 거래 순증감: 수입은 +, 그 외(지출/이체/투자)는 -. */
    @Query(value = """
            select coalesce(sum(case when type = 'INCOME' then amount else -amount end), 0)
            from transaction where account_id = :id
            """, nativeQuery = true)
    long ownNet(@Param("id") Long id);

    /** 상대계좌로 들어온 이체/투자 금액(+). */
    @Query(value = """
            select coalesce(sum(amount), 0)
            from transaction where linked_account_id = :id and type in ('TRANSFER', 'INVEST')
            """, nativeQuery = true)
    long incoming(@Param("id") Long id);

    /** 월별 수입/지출/투자 흐름. [ym, income, expense, invest] */
    @Query(value = """
            select to_char(txn_date, 'YYYY/MM') as ym,
                   coalesce(sum(case when type = 'INCOME'  then amount else 0 end), 0) as income,
                   coalesce(sum(case when type = 'EXPENSE' then amount else 0 end), 0) as expense,
                   coalesce(sum(case when type = 'INVEST'  then amount else 0 end), 0) as invest
            from transaction
            group by ym order by ym
            """, nativeQuery = true)
    List<Object[]> monthlyFlow();

    /** 기간 내 특정 type의 카테고리별 월 합계. [ym, categoryName, amount] */
    @Query(value = """
            select to_char(t.txn_date, 'YYYY/MM') as ym, c.name as name, sum(t.amount) as amount
            from transaction t join category c on t.category_id = c.id
            where t.type = :type and t.txn_date >= :from and t.txn_date < :to
            group by ym, c.name
            order by ym, amount desc
            """, nativeQuery = true)
    List<Object[]> categorySummary(@Param("type") String type,
                                   @Param("from") OffsetDateTime from,
                                   @Param("to") OffsetDateTime to);
}
