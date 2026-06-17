package com.assetmanager.adapter.in.web;

import com.assetmanager.adapter.in.web.dto.CategoryResponse;
import com.assetmanager.adapter.in.web.dto.CreateCategoryRequest;
import com.assetmanager.application.CategoryService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/categories")
@RequiredArgsConstructor
public class CategoryController {

    private final CategoryService categoryService;

    @GetMapping
    public List<CategoryResponse> list() {
        return categoryService.listWithPath().stream().map(CategoryResponse::from).toList();
    }

    @PostMapping
    public CategoryResponse create(@Valid @RequestBody CreateCategoryRequest req) {
        var c = categoryService.create(req.name(), req.type(), req.parentId(), req.sortOrder());
        return new CategoryResponse(c.getId(), c.getName(), c.getType(), c.getParentId(), c.getName());
    }
}
