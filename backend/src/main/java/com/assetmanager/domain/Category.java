package com.assetmanager.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "category")
@Getter
@Setter
@NoArgsConstructor
public class Category {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private CategoryType type;

    /** 상위 카테고리 id. null이면 최상위. 계층 경로는 서비스에서 계산(materialized path 제거). */
    @Column(name = "parent_id")
    private Long parentId;

    @Column(name = "sort_order", nullable = false)
    private int sortOrder = 0;

    public Category(String name, CategoryType type, Long parentId, int sortOrder) {
        this.name = name;
        this.type = type;
        this.parentId = parentId;
        this.sortOrder = sortOrder;
    }
}
