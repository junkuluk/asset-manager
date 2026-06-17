package com.assetmanager.adapter.in.web;

import com.assetmanager.application.DashboardService;
import com.assetmanager.application.DashboardService.CategoryAmount;
import com.assetmanager.application.DashboardService.MonthlyFlow;
import com.assetmanager.domain.TxnType;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/dashboard")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    /** 월별 수입/지출/투자 흐름. */
    @GetMapping("/monthly")
    public List<MonthlyFlow> monthly() {
        return dashboardService.monthlyFlow();
    }

    /** 기간 내 카테고리별 합계(수입 또는 지출). */
    @GetMapping("/category-summary")
    public List<CategoryAmount> categorySummary(
            @RequestParam TxnType type,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        return dashboardService.categorySummary(type, from, to);
    }
}
