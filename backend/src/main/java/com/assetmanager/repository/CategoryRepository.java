package com.assetmanager.repository;

import com.assetmanager.domain.Category;
import com.assetmanager.domain.CategoryType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface CategoryRepository extends JpaRepository<Category, Long> {
    Optional<Category> findByNameAndType(String name, CategoryType type);
    List<Category> findByType(CategoryType type);
}
