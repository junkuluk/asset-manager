import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Transactions from "./pages/Transactions";
import Upload from "./pages/Upload";
import Accounts from "./pages/Accounts";

export default function App() {
  const { loggedIn, logout } = useAuth();

  if (!loggedIn) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    );
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>💰 자산관리</h1>
        <nav>
          <NavLink to="/" end>대시보드</NavLink>
          <NavLink to="/transactions">거래내역</NavLink>
          <NavLink to="/upload">업로드</NavLink>
          <NavLink to="/accounts">계좌</NavLink>
        </nav>
        <button className="logout" onClick={logout}>로그아웃</button>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
