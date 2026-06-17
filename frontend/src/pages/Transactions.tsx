import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Category, Transaction, TxnType } from "../api/types";
import { monthsAgoStart, todayISO, won } from "../util";

const TYPE_LABEL: Record<TxnType, string> = {
  INCOME: "수입",
  EXPENSE: "지출",
  TRANSFER: "이체",
  INVEST: "투자",
};

export default function Transactions() {
  const [from, setFrom] = useState(monthsAgoStart(2));
  const [to, setTo] = useState(todayISO());
  const [typeFilter, setTypeFilter] = useState<"" | TxnType>("");
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ from, to });
      if (typeFilter) params.set("type", typeFilter);
      const data = await api.get<Transaction[]>(`/api/transactions?${params}`);
      setTxns(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "조회 실패");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    api.get<Category[]>("/api/categories").then(setCategories).catch(() => undefined);
  }, []);
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function changeCategory(t: Transaction, categoryId: number) {
    const updated = await api.patch<Transaction>(`/api/transactions/${t.id}`, { categoryId });
    setTxns((prev) => prev.map((x) => (x.id === t.id ? updated : x)));
  }

  return (
    <div>
      <h2>거래내역</h2>
      <div className="card">
        <div className="row">
          <label>
            시작 <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label>
            종료 <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as "" | TxnType)}>
            <option value="">전체 유형</option>
            <option value="EXPENSE">지출</option>
            <option value="INCOME">수입</option>
            <option value="TRANSFER">이체</option>
            <option value="INVEST">투자</option>
          </select>
          <button className="primary" onClick={load}>조회</button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="card">
        {loading ? (
          <p>불러오는 중…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>날짜</th>
                <th>내용</th>
                <th>유형</th>
                <th>계좌</th>
                <th className="num">금액</th>
                <th>카테고리</th>
              </tr>
            </thead>
            <tbody>
              {txns.map((t) => (
                <tr key={t.id}>
                  <td>{t.txnDate.slice(0, 10)}</td>
                  <td>{t.content}</td>
                  <td>
                    <span className={`tag ${t.type}`}>{TYPE_LABEL[t.type]}</span>
                  </td>
                  <td>{t.accountName}</td>
                  <td className="num">{won(t.amount)}</td>
                  <td>
                    {t.type === "EXPENSE" || t.type === "INCOME" ? (
                      <select
                        value={t.categoryId ?? ""}
                        onChange={(e) => changeCategory(t, Number(e.target.value))}
                      >
                        <option value="" disabled>선택</option>
                        {categories
                          .filter((c) => c.type === t.type)
                          .map((c) => (
                            <option key={c.id} value={c.id}>{c.path}</option>
                          ))}
                      </select>
                    ) : (
                      <span className="muted">{t.categoryName ?? "-"}</span>
                    )}
                  </td>
                </tr>
              ))}
              {txns.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">거래가 없습니다.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
