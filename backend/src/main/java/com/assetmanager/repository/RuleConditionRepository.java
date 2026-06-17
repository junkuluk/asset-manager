package com.assetmanager.repository;

import com.assetmanager.domain.RuleCondition;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface RuleConditionRepository extends JpaRepository<RuleCondition, Long> {
    List<RuleCondition> findByRuleId(Long ruleId);
}
