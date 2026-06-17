package com.assetmanager.adapter.in.web.dto;

import com.assetmanager.domain.CategoryType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record CreateCategoryRequest(
        @NotBlank String name,
        @NotNull CategoryType type,
        Long parentId,
        int sortOrder
) {}
