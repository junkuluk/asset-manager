package com.assetmanager.application;

import com.assetmanager.common.NotFoundException;
import com.assetmanager.domain.*;
import com.assetmanager.repository.AccountRepository;
import com.assetmanager.repository.CategoryRepository;
import com.assetmanager.repository.TransactionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class TransactionService {

    private final TransactionRepository transactionRepository;
    private final AccountRepository accountRepository;
    private final CategoryRepository categoryRepository;

    /** 거래 + 표시용 계좌/카테고리 이름. */
    public record TransactionView(Transaction txn, String accountName, String categoryName) {}

    @Transactional(readOnly = true)
    public List<TransactionView> list(LocalDate from, LocalDate to, TxnType type, TxnSource source) {
        OffsetDateTime start = from.atStartOfDay().atZone(java.time.ZoneId.of("Asia/Seoul")).toOffsetDateTime();
        OffsetDateTime end = to.plusDays(1).atStartOfDay().atZone(java.time.ZoneId.of("Asia/Seoul")).toOffsetDateTime();

        Map<Long, String> accountNames = new HashMap<>();
        accountRepository.findAll().forEach(a -> accountNames.put(a.getId(), a.getName()));
        Map<Long, String> categoryNames = new HashMap<>();
        categoryRepository.findAll().forEach(c -> categoryNames.put(c.getId(), c.getName()));

        return transactionRepository.findInRange(start, end).stream()
                .filter(t -> type == null || t.getType() == type)
                .filter(t -> source == null || t.getSource() == source)
                .map(t -> new TransactionView(t,
                        accountNames.get(t.getAccountId()),
                        t.getCategoryId() == null ? null : categoryNames.get(t.getCategoryId())))
                .toList();
    }

    /** 단건 표시용 뷰. */
    @Transactional(readOnly = true)
    public TransactionView view(Long id) {
        Transaction t = transactionRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("거래가 없습니다: " + id));
        String accountName = accountRepository.findById(t.getAccountId())
                .map(Account::getName).orElse(null);
        String categoryName = t.getCategoryId() == null ? null
                : categoryRepository.findById(t.getCategoryId()).map(Category::getName).orElse(null);
        return new TransactionView(t, accountName, categoryName);
    }

    /** 카테고리/메모 직접 수정. 카테고리를 바꾸면 수동분류로 표시(규칙 재적용 제외). */
    @Transactional
    public Transaction update(Long id, Long categoryId, String memo) {
        Transaction t = transactionRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("거래가 없습니다: " + id));
        if (categoryId != null) {
            t.setCategoryId(categoryId);
            t.setManualCategory(true);
        }
        if (memo != null) {
            t.setMemo(memo);
        }
        return t;
    }

    /** 지출 거래를 이체/투자로 재분류하고 상대 계좌를 연결. */
    @Transactional
    public Transaction reclassify(Long id, Long linkedAccountId) {
        Transaction t = transactionRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("거래가 없습니다: " + id));
        if (t.getType() != TxnType.EXPENSE) {
            throw new IllegalArgumentException("지출 거래만 이체로 재분류할 수 있습니다.");
        }
        Account linked = accountRepository.findById(linkedAccountId)
                .orElseThrow(() -> new NotFoundException("연결 계좌가 없습니다: " + linkedAccountId));

        t.setType(linked.getType() == AccountType.INVEST ? TxnType.INVEST : TxnType.TRANSFER);
        t.setLinkedAccountId(linkedAccountId);
        t.setCategoryId(null);
        t.setManualCategory(true);
        return t;
    }
}
