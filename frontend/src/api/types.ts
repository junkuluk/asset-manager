export type TxnType = "INCOME" | "EXPENSE" | "TRANSFER" | "INVEST";
export type TxnSource = "CARD" | "BANK" | "MANUAL";
export type AccountType = "BANK" | "CARD" | "INVEST" | "CASH";
export type CategoryType = "INCOME" | "EXPENSE";

export interface Account {
  id: number;
  name: string;
  type: AccountType;
  asset: boolean;
  initialBalance: number;
  balance: number;
}

export interface Category {
  id: number;
  name: string;
  type: CategoryType;
  parentId: number | null;
  path: string;
}

export interface Transaction {
  id: number;
  txnDate: string;
  type: TxnType;
  source: TxnSource;
  amount: number;
  content: string | null;
  memo: string | null;
  merchant: string | null;
  accountId: number;
  accountName: string | null;
  categoryId: number | null;
  categoryName: string | null;
  linkedAccountId: number | null;
  manualCategory: boolean;
  cardName: string | null;
}

export interface MonthlyFlow {
  month: string;
  income: number;
  expense: number;
  invest: number;
}

export interface CategoryAmount {
  month: string;
  category: string;
  amount: number;
}

export interface ImportResult {
  inserted: number;
  skipped: number;
}
