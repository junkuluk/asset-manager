package com.assetmanager.application;

import com.assetmanager.domain.*;
import com.assetmanager.repository.RuleConditionRepository;
import com.assetmanager.repository.RuleRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * 거래 자동 분류/이체 식별 엔진.
 *
 * <p>기존 파이썬의 run_rule_engine + identify_transfers 두 함수를 하나로 통합했다.
 * 우선순위(priority) 오름차순으로 규칙을 평가하고, 모든 조건이 AND로 만족되는
 * 첫 규칙의 action(CATEGORIZE/TRANSFER)을 적용한다. 한 번 분류된 거래는 다음 규칙에서 건너뛴다.
 */
@Service
@RequiredArgsConstructor
public class RuleEngine {

    private final RuleRepository ruleRepository;
    private final RuleConditionRepository conditionRepository;

    /** 적용에 필요한 규칙+조건을 미리 묶어 둔 스냅샷. 업로드 한 배치 동안 재사용. */
    public record LoadedRule(Rule rule, List<RuleCondition> conditions) {}

    @Transactional(readOnly = true)
    public List<LoadedRule> load() {
        Map<Long, List<RuleCondition>> byRule = conditionRepository.findAll().stream()
                .collect(Collectors.groupingBy(RuleCondition::getRuleId));
        return ruleRepository.findAllByOrderByPriorityAsc().stream()
                .map(r -> new LoadedRule(r, byRule.getOrDefault(r.getId(), List.of())))
                .toList();
    }

    /**
     * 단일 거래에 규칙을 적용한다. 매칭되는 첫 규칙의 동작을 적용하고 종료.
     * 이미 사용자가 수동 분류한 거래는 건드리지 않는다.
     *
     * @param transferCategoryId 이체로 분류될 때 부여할 카테고리(예: 카드대금 이체)
     */
    public void apply(Transaction txn, List<LoadedRule> rules, Long transferCategoryId) {
        if (txn.isManualCategory()) {
            return;
        }
        for (LoadedRule lr : rules) {
            if (lr.conditions().isEmpty()) {
                continue;
            }
            if (matchesAll(txn, lr.conditions())) {
                applyAction(txn, lr.rule(), transferCategoryId);
                return;
            }
        }
    }

    private void applyAction(Transaction txn, Rule rule, Long transferCategoryId) {
        if (rule.getAction() == RuleAction.CATEGORIZE) {
            txn.setCategoryId(rule.getCategoryId());
        } else if (rule.getAction() == RuleAction.TRANSFER) {
            txn.setType(TxnType.TRANSFER);
            txn.setLinkedAccountId(rule.getLinkedAccountId());
            if (transferCategoryId != null) {
                txn.setCategoryId(transferCategoryId);
            }
        }
    }

    private boolean matchesAll(Transaction txn, List<RuleCondition> conditions) {
        for (RuleCondition c : conditions) {
            if (!matches(txn, c)) {
                return false;
            }
        }
        return true;
    }

    private boolean matches(Transaction txn, RuleCondition c) {
        String text = fieldValue(txn, c.getField());
        return switch (c.getMatchType()) {
            case CONTAINS -> text != null && text.contains(c.getValue());
            case EXACT -> text != null && text.strip().equals(c.getValue());
            case REGEX -> text != null && Pattern
                    .compile(c.getValue(), Pattern.CASE_INSENSITIVE)
                    .matcher(text).find();
            case GT -> numeric(text) > parseLong(c.getValue());
            case LT -> numeric(text) < parseLong(c.getValue());
            case EQ -> numeric(text) == parseLong(c.getValue());
        };
    }

    /** 규칙 조건이 참조할 수 있는 거래 필드. */
    private String fieldValue(Transaction txn, String field) {
        return switch (field) {
            case "content" -> txn.getContent();
            case "merchant" -> txn.getMerchant();
            case "amount", "transaction_amount" -> String.valueOf(txn.getAmount());
            default -> null;
        };
    }

    private long numeric(String s) {
        try {
            return s == null ? Long.MIN_VALUE : (long) Double.parseDouble(s.replace(",", ""));
        } catch (NumberFormatException e) {
            return Long.MIN_VALUE;
        }
    }

    private long parseLong(String s) {
        return Long.parseLong(s.strip());
    }
}
