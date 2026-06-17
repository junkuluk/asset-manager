package com.assetmanager.adapter.out.excel;

import com.assetmanager.domain.TxnSource;
import com.assetmanager.port.ParsedRow;
import com.assetmanager.port.StatementParser;
import org.apache.poi.ss.usermodel.*;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.time.LocalDate;
import java.util.*;

/** 신한카드 엑셀 파서. 헤더명으로 컬럼을 찾는다. */
@Component
public class ShinhanCardParser implements StatementParser {

    @Override
    public TxnSource source() {
        return TxnSource.CARD;
    }

    @Override
    public boolean supports(String filename) {
        String f = filename == null ? "" : filename.toLowerCase();
        return f.contains("shinhancard") || f.contains("shinhan");
    }

    @Override
    public String accountName(ParsedRow row) {
        return "신한카드";
    }

    @Override
    public List<ParsedRow> parse(InputStream in) {
        try (Workbook wb = WorkbookFactory.create(in)) {
            Sheet sheet = wb.getSheetAt(0);
            Map<String, Integer> col = headerIndex(sheet.getRow(sheet.getFirstRowNum()));
            int cDate = col.getOrDefault("거래일", -1);
            int cContent = col.getOrDefault("가맹점명", -1);
            int cAmount = col.getOrDefault("금액", -1);
            int cCardName = col.getOrDefault("이용카드", -1);
            int cApproval = col.getOrDefault("승인번호", -1);
            int cKind = col.getOrDefault("카드구분", -1);

            List<ParsedRow> rows = new ArrayList<>();
            int start = sheet.getFirstRowNum() + 1;
            for (int i = start; i <= sheet.getLastRowNum(); i++) {
                Row r = sheet.getRow(i);
                if (r == null) continue;
                LocalDate date = PoiCells.date(r, cDate);
                String content = PoiCells.str(r, cContent);
                long amount = PoiCells.money(r, cAmount);
                if (date == null || content == null || amount == 0) continue;

                String kind = cKind >= 0 ? PoiCells.str(r, cKind) : "신용";
                if ("체크".equals(kind)) continue; // 기존 로직: 체크카드는 은행 출금과 중복되므로 제외

                String approval = cApproval >= 0 ? PoiCells.str(r, cApproval) : null;
                String cardName = cCardName >= 0 ? PoiCells.str(r, cCardName) : null;
                String naturalKey = "SHINHAN_CARD:" + approval + ":" + amount + ":" + date;

                rows.add(ParsedRow.card(
                        date.atStartOfDay().atZone(PoiCells.KST).toOffsetDateTime(),
                        amount, content, approval, cardName, kind, naturalKey));
            }
            return rows;
        } catch (Exception e) {
            throw new IllegalArgumentException("신한카드 파일 파싱 실패: " + e.getMessage(), e);
        }
    }

    static Map<String, Integer> headerIndex(Row header) {
        Map<String, Integer> map = new HashMap<>();
        if (header == null) return map;
        for (int i = header.getFirstCellNum(); i < header.getLastCellNum(); i++) {
            String h = PoiCells.str(header, i);
            if (h != null) map.put(h.replace("(원)", "").strip(), i);
        }
        return map;
    }
}
