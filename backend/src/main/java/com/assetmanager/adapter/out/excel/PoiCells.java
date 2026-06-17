package com.assetmanager.adapter.out.excel;

import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.DateUtil;
import org.apache.poi.ss.usermodel.Row;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;

/** POI 셀 값을 안전하게 읽는 정적 헬퍼. */
final class PoiCells {

    static final ZoneId KST = ZoneId.of("Asia/Seoul");

    private PoiCells() {}

    static Cell cell(Row row, int idx) {
        return row == null ? null : row.getCell(idx);
    }

    static String str(Row row, int idx) {
        Cell c = cell(row, idx);
        if (c == null) return null;
        return switch (c.getCellType()) {
            case STRING -> c.getStringCellValue().strip();
            case NUMERIC -> {
                double d = c.getNumericCellValue();
                yield d == Math.floor(d) ? String.valueOf((long) d) : String.valueOf(d);
            }
            case BOOLEAN -> String.valueOf(c.getBooleanCellValue());
            case FORMULA -> {
                try {
                    yield c.getStringCellValue().strip();
                } catch (IllegalStateException e) {
                    yield String.valueOf((long) c.getNumericCellValue());
                }
            }
            default -> null;
        };
    }

    /** "1,234" 같은 문자열/숫자를 long으로. 빈 값은 0. */
    static long money(Row row, int idx) {
        Cell c = cell(row, idx);
        if (c == null) return 0;
        if (c.getCellType() == org.apache.poi.ss.usermodel.CellType.NUMERIC) {
            return (long) c.getNumericCellValue();
        }
        String s = str(row, idx);
        if (s == null || s.isBlank()) return 0;
        s = s.replace(",", "").replace("원", "").strip();
        if (s.isBlank() || s.equals("-")) return 0;
        try {
            return (long) Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    /** 날짜 셀(숫자 날짜 또는 "yyyy-MM-dd"/"yyyy.MM.dd" 문자열)을 LocalDate로. */
    static LocalDate date(Row row, int idx) {
        Cell c = cell(row, idx);
        if (c == null) return null;
        if (c.getCellType() == org.apache.poi.ss.usermodel.CellType.NUMERIC
                && DateUtil.isCellDateFormatted(c)) {
            return c.getLocalDateTimeCellValue().toLocalDate();
        }
        String s = str(row, idx);
        if (s == null || s.isBlank()) return null;
        s = s.replace(".", "-").replace("/", "-").strip();
        // "2024-07-13 12:00:00" 형태면 날짜 부분만
        if (s.length() >= 10) s = s.substring(0, 10);
        try {
            return LocalDate.parse(s);
        } catch (Exception e) {
            return null;
        }
    }

    /** "12:34:56" 또는 "1234" 형태의 시간 문자열을 합쳐 LocalDateTime 구성. */
    static LocalDateTime dateTime(LocalDate date, String timeText) {
        if (date == null) return null;
        if (timeText == null || timeText.isBlank()) return date.atStartOfDay();
        String t = timeText.strip();
        try {
            if (t.contains(":")) {
                String[] p = t.split(":");
                int h = Integer.parseInt(p[0].strip());
                int m = p.length > 1 ? Integer.parseInt(p[1].strip()) : 0;
                int s = p.length > 2 ? Integer.parseInt(p[2].strip().substring(0, Math.min(2, p[2].strip().length()))) : 0;
                return date.atTime(h, m, s);
            }
            String digits = t.replaceAll("\\D", "");
            if (digits.length() >= 4) {
                int h = Integer.parseInt(digits.substring(0, 2));
                int m = Integer.parseInt(digits.substring(2, 4));
                int s = digits.length() >= 6 ? Integer.parseInt(digits.substring(4, 6)) : 0;
                return date.atTime(h, m, s);
            }
        } catch (Exception ignored) {
            // fall through
        }
        return date.atStartOfDay();
    }
}
