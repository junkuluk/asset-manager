package com.assetmanager.adapter.in.web;

import com.assetmanager.application.ImportResult;
import com.assetmanager.application.ImportService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.UncheckedIOException;

@RestController
@RequestMapping("/api/imports")
@RequiredArgsConstructor
public class ImportController {

    private final ImportService importService;

    /** 카드/은행 엑셀 업로드. 파일명으로 적절한 파서를 자동 선택. */
    @PostMapping
    public ImportResult upload(@RequestParam("file") MultipartFile file) {
        try {
            return importService.importStatement(file.getOriginalFilename(), file.getInputStream());
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }
}
