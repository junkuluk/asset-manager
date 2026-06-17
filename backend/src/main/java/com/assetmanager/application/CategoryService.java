package com.assetmanager.application;

import com.assetmanager.common.NotFoundException;
import com.assetmanager.domain.Category;
import com.assetmanager.domain.CategoryType;
import com.assetmanager.repository.CategoryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

@Service
@RequiredArgsConstructor
public class CategoryService {

    private final CategoryRepository categoryRepository;

    /** 카테고리 + 계산된 전체 경로(예: "지출/식비/외식비"). */
    public record CategoryView(Category category, String path) {}

    @Transactional(readOnly = true)
    public List<CategoryView> listWithPath() {
        List<Category> all = categoryRepository.findAll();
        Map<Long, Category> byId = new HashMap<>();
        for (Category c : all) byId.put(c.getId(), c);
        return all.stream()
                .map(c -> new CategoryView(c, pathOf(c, byId)))
                .sorted(Comparator.comparing(CategoryView::path))
                .toList();
    }

    /** parent_id를 따라 루트까지 올라가며 이름 경로를 만든다(순환 방지). */
    private String pathOf(Category c, Map<Long, Category> byId) {
        Deque<String> parts = new ArrayDeque<>();
        Set<Long> seen = new HashSet<>();
        Category cur = c;
        while (cur != null && seen.add(cur.getId())) {
            parts.addFirst(cur.getName());
            cur = cur.getParentId() == null ? null : byId.get(cur.getParentId());
        }
        return String.join("/", parts);
    }

    @Transactional
    public Category create(String name, CategoryType type, Long parentId, int sortOrder) {
        if (parentId != null && categoryRepository.findById(parentId).isEmpty()) {
            throw new NotFoundException("상위 카테고리가 없습니다: " + parentId);
        }
        return categoryRepository.save(new Category(name, type, parentId, sortOrder));
    }
}
