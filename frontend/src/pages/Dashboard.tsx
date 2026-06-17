import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { MonthlyFlow } from "../api/types";
import { won } from "../util";

export default function Dashboard() {
  const [flow, setFlow] = useState<MonthlyFlow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<MonthlyFlow[]>("/api/dashboard/monthly").then(setFlow).catch((e) => setError(e.message));
  }, []);

  const recent = flow[flow.length - 1];
  const totalIncome = flow.reduce((s, f) => s + f.income, 0);
  const totalExpense = flow.reduce((s, f) => s + f.expense, 0);

  return (
    <div>
      <h2>대시보드</h2>
      {error && <p className="error">{error}</p>}

      <div className="kpi">
        <div className="card">
          <div className="label">이번 달 수입</div>
          <div className="value" style={{ color: "var(--income)" }}>
            {won(recent?.income ?? 0)}
          </div>
        </div>
        <div className="card">
          <div className="label">이번 달 지출</div>
          <div className="value" style={{ color: "var(--expense)" }}>
            {won(recent?.expense ?? 0)}
          </div>
        </div>
        <div className="card">
          <div className="label">누적 수입 - 지출</div>
          <div className="value">{won(totalIncome - totalExpense)}</div>
        </div>
      </div>

      <div className="card">
        <h3>월별 수입 / 지출 / 투자</h3>
        {flow.length === 0 ? (
          <p className="muted">데이터가 없습니다. 먼저 엑셀을 업로드하세요.</p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={flow}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={(v) => `${(v / 10000).toLocaleString()}만`} width={70} />
              <Tooltip formatter={(v: number) => won(v)} />
              <Legend />
              <Bar dataKey="income" name="수입" fill="#16a34a" />
              <Bar dataKey="expense" name="지출" fill="#dc2626" />
              <Bar dataKey="invest" name="투자" fill="#9333ea" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
