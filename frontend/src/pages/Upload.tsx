import { useState } from "react";
import { api } from "../api/client";
import type { ImportResult } from "../api/types";

export default function Upload() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onFile(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.upload<ImportResult>("/api/imports", file);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드 실패");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>업로드</h2>
      <div className="card">
        <p className="muted">
          신한카드 / 국민카드 / 신한은행 엑셀(.xls, .xlsx)을 올리면 자동으로 분류·저장됩니다.
          파일명으로 출처를 인식합니다. 중복 거래는 자동으로 건너뜁니다.
        </p>
        <input
          type="file"
          accept=".xls,.xlsx"
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFile(f);
            e.target.value = "";
          }}
        />
        {busy && <p>처리 중…</p>}
        {error && <p className="error">{error}</p>}
        {result && (
          <p>
            ✅ 추가 <b>{result.inserted}</b>건 / 중복 건너뜀 <b>{result.skipped}</b>건
          </p>
        )}
      </div>
    </div>
  );
}
