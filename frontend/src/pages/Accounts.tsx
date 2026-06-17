import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Account } from "../api/types";
import { won } from "../util";

export default function Accounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Account[]>("/api/accounts").then(setAccounts).catch((e) => setError(e.message));
  }, []);

  const netAsset = accounts
    .filter((a) => a.asset)
    .reduce((sum, a) => sum + a.balance, 0);

  return (
    <div>
      <h2>계좌</h2>
      {error && <p className="error">{error}</p>}
      <div className="kpi">
        <div className="card">
          <div className="label">순자산 (자산 계좌 합계)</div>
          <div className="value">{won(netAsset)}</div>
        </div>
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>이름</th>
              <th>유형</th>
              <th>자산/부채</th>
              <th className="num">현재 잔액</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id}>
                <td>{a.name}</td>
                <td>{a.type}</td>
                <td>{a.asset ? "자산" : "부채"}</td>
                <td className="num">{won(a.balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
