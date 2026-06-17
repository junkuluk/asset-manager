package com.assetmanager.application;

import com.assetmanager.domain.TxnType;
import com.assetmanager.repository.TransactionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;

@Service
@RequiredArgsConstructor
public class DashboardService {

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private final TransactionRepository transactionRepository;

    public record MonthlyFlow(String month, long income, long expense, long invest) {}
    public record CategoryAmount(String month, String category, long amount) {}

    @Transactional(readOnly = true)
    public List<MonthlyFlow> monthlyFlow() {
        return transactionRepository.monthlyFlow().stream()
                .map(r -> new MonthlyFlow(
                        (String) r[0],
                        ((Number) r[1]).longValue(),
                        ((Number) r[2]).longValue(),
                        ((Number) r[3]).longValue()))
                .toList();
    }

    @Transactional(readOnly = true)
    public List<CategoryAmount> categorySummary(TxnType type, LocalDate from, LocalDate to) {
        OffsetDateTime start = from.atStartOfDay().atZone(KST).toOffsetDateTime();
        OffsetDateTime end = to.plusDays(1).atStartOfDay().atZone(KST).toOffsetDateTime();
        return transactionRepository.categorySummary(type.name(), start, end).stream()
                .map(r -> new CategoryAmount(
                        (String) r[0],
                        (String) r[1],
                        ((Number) r[2]).longValue()))
                .toList();
    }
}
