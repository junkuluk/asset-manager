package com.assetmanager.application;

import com.assetmanager.domain.*;
import com.assetmanager.port.ParsedRow;
import com.assetmanager.port.StatementParser;
import com.assetmanager.repository.AccountRepository;
import com.assetmanager.repository.CategoryRepository;
import com.assetmanager.repository.TransactionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.io.InputStream;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 엑셀 업로드 오케스트레이션: 파서선택 → 파싱 → 중복제거 → 거래변환 → 규칙엔진 → 저장.
 * 잔액 이력 테이블이 없으므로 저장만 하면 되고, 잔액은 조회 시 계산한다.
 */
@Service
@RequiredArgsConstructor
public class ImportService {

    private final List<StatementParser> parsers;
    private final AccountRepository accountRepository;
    private final CategoryRepository categoryRepository;
    private final TransactionRepository transactionRepository;
    private final RuleEngine ruleEngine;

    @Transactional
    public ImportResult importStatement(String filename, InputStream in) {
        StatementParser parser = parsers.stream()
                .filter(p -> p.supports(filename))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("지원하지 않는 파일 형식: " + filename));

        List<ParsedRow> rows;
        try (InputStream stream = in) {
            rows = parser.parse(stream);
        } catch (IOException e) {
            throw new IllegalArgumentException("파일 읽기 실패: " + e.getMessage(), e);
        }
        if (rows.isEmpty()) {
            return new ImportResult(0, 0);
        }

        // 1) 중복 제거 (DB에 이미 있는 해시 + 같은 파일 내 중복)
        Set<String> incoming = rows.stream().map(ParsedRow::naturalKey).collect(Collectors.toSet());
        Set<String> existing = transactionRepository.findExistingHashes(incoming);

        // 2) 사전 로딩
        Long expenseDefault = categoryId("미분류", CategoryType.EXPENSE);
        Long incomeDefault = categoryId("미분류", CategoryType.INCOME);
        List<RuleEngine.LoadedRule> loadedRules = ruleEngine.load();
        Map<String, Long> accountIdCache = new HashMap<>();

        int inserted = 0;
        int skipped = 0;
        Set<String> seenInBatch = new HashSet<>();

        for (ParsedRow row : rows) {
            if (existing.contains(row.naturalKey()) || !seenInBatch.add(row.naturalKey())) {
                skipped++;
                continue;
            }
            Long accountId = accountIdCache.computeIfAbsent(parser.accountName(row),
                    name -> accountRepository.findByName(name)
                            .orElseThrow(() -> new IllegalStateException("계좌를 찾을 수 없습니다: " + name))
                            .getId());

            Transaction txn = toTransaction(row, parser.source(), accountId, expenseDefault, incomeDefault);
            // 이체 분류는 카테고리 없이 표시(transferCategoryId=null), 분류 규칙은 category 부여
            ruleEngine.apply(txn, loadedRules, null);
            transactionRepository.save(txn);
            inserted++;
        }
        return new ImportResult(inserted, skipped);
    }

    private Transaction toTransaction(ParsedRow row, TxnSource source, Long accountId,
                                      Long expenseDefault, Long incomeDefault) {
        Transaction t = new Transaction();
        t.setAccountId(accountId);
        t.setSource(source);
        t.setTxnDate(row.date());
        t.setAmount(row.amount());
        t.setContent(row.content());
        t.setMerchant(row.merchant());
        t.setDedupHash(row.naturalKey());
        t.setCardApprovalNo(row.cardApprovalNo());
        t.setCardName(row.cardName());
        t.setCardKind(row.cardKind());
        t.setBankBranch(row.bankBranch());

        if (row.income()) {
            t.setType(TxnType.INCOME);
            t.setCategoryId(incomeDefault);
        } else {
            t.setType(TxnType.EXPENSE);
            t.setCategoryId(expenseDefault);
        }
        return t;
    }

    private Long categoryId(String name, CategoryType type) {
        return categoryRepository.findByNameAndType(name, type)
                .map(Category::getId)
                .orElse(null);
    }
}
