package com.assetmanager.adapter.out.excel;

import com.assetmanager.domain.TxnSource;
import com.assetmanager.port.ParsedRow;
import com.assetmanager.port.StatementParser;
import org.apache.poi.ss.usermodel.*;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * 국민카드 엑셀 파서. 기존 로직: 6행 건너뛰고 컬럼 인덱스 [0,3,4,5,13]을
 * 거래일/이용카드/내용/금액/승인번호로 사용. 카드구분은 신용 고정.
 */
@Component
public class KookminCardParser implements StatementParser {

    private static final int SKIP_ROWS = 6;
    private static final int C_DATE = 0, C_CARD_NAME = 3, C_CONTENT = 4, C_AMOUNT = 5, C_APPROVAL = 13;

    @Override
    public TxnSource source() {
        return TxnSource.CARD;
    }

    @Override
    public boolean supports(String filename) {
        String f = filename == null ? "" : filename.toLowerCase();
        return f.contains("kookmin") || f.contains("kukmin") || f.contains("국민");
    }

    @Override
    public String accountName(ParsedRow row) {
        return "국민카드";
    }

    @Override
    public List<ParsedRow> parse(InputStream in) {
        try (Workbook wb = WorkbookFactory.create(in)) {
            Sheet sheet = wb.getSheetAt(0);
            List<ParsedRow> rows = new ArrayList<>();
            for (int i = SKIP_ROWS; i <= sheet.getLastRowNum(); i++) {
                Row r = sheet.getRow(i);
                if (r == null) continue;
                LocalDate date = PoiCells.date(r, C_DATE);
                String content = PoiCells.str(r, C_CONTENT);
                long amount = PoiCells.money(r, C_AMOUNT);
                if (date == null || content == null || amount == 0) continue;

                String approval = PoiCells.str(r, C_APPROVAL);
                String cardName = PoiCells.str(r, C_CARD_NAME);
                String naturalKey = "KOOKMIN_CARD:" + approval + ":" + amount + ":" + date;

                rows.add(ParsedRow.card(
                        date.atStartOfDay().atZone(PoiCells.KST).toOffsetDateTime(),
                        amount, content, approval, cardName, "신용", naturalKey));
            }
            return rows;
        } catch (Exception e) {
            throw new IllegalArgumentException("국민카드 파일 파싱 실패: " + e.getMessage(), e);
        }
    }
}
