package com.assetmanager.adapter.in.web;

import com.assetmanager.adapter.in.web.dto.ReclassifyRequest;
import com.assetmanager.adapter.in.web.dto.TransactionResponse;
import com.assetmanager.adapter.in.web.dto.UpdateTransactionRequest;
import com.assetmanager.application.TransactionService;
import com.assetmanager.domain.TxnSource;
import com.assetmanager.domain.TxnType;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/transactions")
@RequiredArgsConstructor
public class TransactionController {

    private final TransactionService transactionService;

    @GetMapping
    public List<TransactionResponse> list(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
            @RequestParam(required = false) TxnType type,
            @RequestParam(required = false) TxnSource source) {
        return transactionService.list(from, to, type, source).stream()
                .map(TransactionResponse::from).toList();
    }

    @PatchMapping("/{id}")
    public TransactionResponse update(@PathVariable Long id,
                                      @RequestBody UpdateTransactionRequest req) {
        var t = transactionService.update(id, req.categoryId(), req.memo());
        return TransactionResponse.from(transactionService.view(t.getId()));
    }

    @PostMapping("/{id}/reclassify")
    public TransactionResponse reclassify(@PathVariable Long id,
                                          @Valid @RequestBody ReclassifyRequest req) {
        var t = transactionService.reclassify(id, req.linkedAccountId());
        return TransactionResponse.from(transactionService.view(t.getId()));
    }
}
