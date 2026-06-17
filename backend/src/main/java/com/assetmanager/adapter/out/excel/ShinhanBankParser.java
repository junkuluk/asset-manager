package com.assetmanager.adapter.out.excel;

import com.assetmanager.domain.TxnSource;
import com.assetmanager.port.ParsedRow;
import com.assetmanager.port.StatementParser;
import org.apache.poi.ss.usermodel.*;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 신한은행 거래내역 엑셀 파서. 기존 로직: 6행 건너뛴 행이 헤더, 컬럼명에서 "(원)" 제거.
 * 입금>0 이면 수입, 출금>0 이면 지출. 이체 식별은 이후 규칙엔진이 수행.
 */
@Component
public class ShinhanBankParser implements StatementParser {

    private static final int HEADER_ROW = 6;

    @Override
    public TxnSource source() {
        return TxnSource.BANK;
    }

    @Override
    public boolean supports(String filename) {
        String f = filename == null ? "" : filename.toLowerCase();
        return f.contains("은행") || f.contains("거래내역") || f.contains("bank");
    }

    @Override
    public String accountName(ParsedRow row) {
        return "신한은행";
    }

    @Override
    public List<ParsedRow> parse(InputStream in) {
        try (Workbook wb = WorkbookFactory.create(in)) {
            Sheet sheet = wb.getSheetAt(0);
            Map<String, Integer> col = ShinhanCardParser.headerIndex(sheet.getRow(HEADER_ROW));
            int cDate = col.getOrDefault("거래일자", -1);
            int cTime = col.getOrDefault("거래시간", -1);
            int cOut = col.getOrDefault("출금", -1);
            int cIn = col.getOrDefault("입금", -1);
            int cContent = col.getOrDefault("내용", -1);
            int cSummary = col.getOrDefault("적요", -1);
            int cBranch = col.getOrDefault("거래점", -1);

            List<ParsedRow> rows = new ArrayList<>();
            for (int i = HEADER_ROW + 1; i <= sheet.getLastRowNum(); i++) {
                Row r = sheet.getRow(i);
                if (r == null) continue;
                LocalDate date = PoiCells.date(r, cDate);
                if (date == null) continue;
                String timeText = cTime >= 0 ? PoiCells.str(r, cTime) : null;
                long withdraw = PoiCells.money(r, cOut);
                long deposit = PoiCells.money(r, cIn);
                if (withdraw == 0 && deposit == 0) continue;

                boolean income = deposit > 0;
                long amount = income ? deposit : withdraw;
                String content = cContent >= 0 ? PoiCells.str(r, cContent) : null;
                String summary = cSummary >= 0 ? PoiCells.str(r, cSummary) : null;
                String branch = cBranch >= 0 ? PoiCells.str(r, cBranch) : null;

                LocalDateTime dt = PoiCells.dateTime(date, timeText);
                // 기존 dedup 해시: 날짜-시간-출금-입금
                String naturalKey = "SHINHAN_BANK:" + date + "-" + (timeText == null ? "" : timeText)
                        + "-" + withdraw + "-" + deposit;

                rows.add(ParsedRow.bank(
                        dt.atZone(PoiCells.KST).toOffsetDateTime(),
                        amount, income, content, summary, branch, naturalKey));
            }
            return rows;
        } catch (Exception e) {
            throw new IllegalArgumentException("신한은행 파일 파싱 실패: " + e.getMessage(), e);
        }
    }
}
