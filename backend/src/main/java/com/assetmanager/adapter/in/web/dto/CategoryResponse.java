package com.assetmanager.adapter.in.web.dto;

import com.assetmanager.application.CategoryService.CategoryView;
import com.assetmanager.domain.CategoryType;

public record CategoryResponse(
        Long id,
        String name,
        CategoryType type,
        Long parentId,
        String path
) {
    public static CategoryResponse from(CategoryView v) {
        return new CategoryResponse(
                v.category().getId(), v.category().getName(), v.category().getType(),
                v.category().getParentId(), v.path());
    }
}
