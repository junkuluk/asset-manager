package com.assetmanager.application;

import com.assetmanager.domain.*;
import com.assetmanager.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 최초 1회 기본 데이터 시드. 테이블이 비어 있을 때만 동작.
 * 기존의 4단계 깊은 카테고리 대신 2단계로 간소화했고, 필요한 분류는 UI에서 추가하면 된다.
 */
@Component
@RequiredArgsConstructor
public class DataSeeder implements CommandLineRunner {

    private final AccountRepository accountRepository;
    private final CategoryRepository categoryRepository;
    private final RuleRepository ruleRepository;
    private final RuleConditionRepository conditionRepository;

    @Override
    @Transactional
    public void run(String... args) {
        if (accountRepository.count() == 0) seedAccounts();
        if (categoryRepository.count() == 0) seedCategories();
        if (ruleRepository.count() == 0) seedRules();
    }

    private void seedAccounts() {
        accountRepository.saveAll(List.of(
                new Account("신한은행", AccountType.BANK, true, 0),
                new Account("신한카드", AccountType.CARD, false, 0),
                new Account("국민카드", AccountType.CARD, false, 0),
                new Account("현금", AccountType.CASH, true, 0),
                new Account("증권계좌", AccountType.INVEST, true, 0)
        ));
    }

    private void seedCategories() {
        // 지출
        save("미분류", CategoryType.EXPENSE, null);
        Category fixed = save("고정지출", CategoryType.EXPENSE, null);
        save("통신비", CategoryType.EXPENSE, fixed.getId());
        save("보험료", CategoryType.EXPENSE, fixed.getId());
        save("주거비", CategoryType.EXPENSE, fixed.getId());
        save("공과금", CategoryType.EXPENSE, fixed.getId());

        Category variable = save("변동지출", CategoryType.EXPENSE, null);
        Category food = save("식비", CategoryType.EXPENSE, variable.getId());
        save("외식비", CategoryType.EXPENSE, food.getId());
        save("편의점", CategoryType.EXPENSE, food.getId());
        save("마트", CategoryType.EXPENSE, food.getId());
        save("배달비", CategoryType.EXPENSE, food.getId());
        save("생활비", CategoryType.EXPENSE, variable.getId());
        Category medical = save("의료비", CategoryType.EXPENSE, variable.getId());
        save("병원비", CategoryType.EXPENSE, medical.getId());
        save("약국", CategoryType.EXPENSE, medical.getId());
        Category car = save("교통/차량", CategoryType.EXPENSE, variable.getId());
        save("대중교통", CategoryType.EXPENSE, car.getId());
        save("주유비", CategoryType.EXPENSE, car.getId());

        // 수입
        save("미분류", CategoryType.INCOME, null);
        save("급여", CategoryType.INCOME, null);
        save("금융수입", CategoryType.INCOME, null);
        save("기타수입", CategoryType.INCOME, null);
    }

    private Category save(String name, CategoryType type, Long parentId) {
        return categoryRepository.save(new Category(name, type, parentId, 0));
    }

    private void seedRules() {
        Long shinhanCard = accountId("신한카드");
        Long kookminCard = accountId("국민카드");

        // 이체(카드대금) 식별 규칙: 은행 content/merchant 기준
        transferRule("신한카드 대금", shinhanCard,
                cond("merchant", MatchType.EXACT, "카드결"),
                cond("content", MatchType.EXACT, "신한카드"));
        transferRule("국민카드 대금", kookminCard,
                cond("merchant", MatchType.EXACT, "FB카드"),
                cond("content", MatchType.CONTAINS, "KB카드"));

        // 분류 규칙(대표 예시) — 나머지는 UI에서 추가
        categorizeRule("편의점", categoryId("편의점", CategoryType.EXPENSE),
                cond("content", MatchType.CONTAINS, "GS25"));
        categorizeRule("편의점", categoryId("편의점", CategoryType.EXPENSE),
                cond("content", MatchType.CONTAINS, "CU"));
        categorizeRule("마트", categoryId("마트", CategoryType.EXPENSE),
                cond("content", MatchType.CONTAINS, "이마트"));
        categorizeRule("약국", categoryId("약국", CategoryType.EXPENSE),
                cond("content", MatchType.CONTAINS, "약국"));
        categorizeRule("주유", categoryId("주유비", CategoryType.EXPENSE),
                cond("content", MatchType.CONTAINS, "주유소"));
        categorizeRule("대중교통", categoryId("대중교통", CategoryType.EXPENSE),
                cond("content", MatchType.CONTAINS, "티머니"));
    }

    private void transferRule(String name, Long linkedAccountId, RuleCondition... conds) {
        Rule r = new Rule();
        r.setName(name);
        r.setPriority(1);
        r.setAction(RuleAction.TRANSFER);
        r.setLinkedAccountId(linkedAccountId);
        persistRule(r, conds);
    }

    private void categorizeRule(String name, Long categoryId, RuleCondition... conds) {
        Rule r = new Rule();
        r.setName(name);
        r.setPriority(5);
        r.setAction(RuleAction.CATEGORIZE);
        r.setCategoryId(categoryId);
        persistRule(r, conds);
    }

    private void persistRule(Rule r, RuleCondition... conds) {
        Rule saved = ruleRepository.save(r);
        for (RuleCondition c : conds) {
            c.setRuleId(saved.getId());
            conditionRepository.save(c);
        }
    }

    private RuleCondition cond(String field, MatchType type, String value) {
        RuleCondition c = new RuleCondition();
        c.setField(field);
        c.setMatchType(type);
        c.setValue(value);
        return c;
    }

    private Long accountId(String name) {
        return accountRepository.findByName(name).orElseThrow().getId();
    }

    private Long categoryId(String name, CategoryType type) {
        return categoryRepository.findByNameAndType(name, type).orElseThrow().getId();
    }
}
