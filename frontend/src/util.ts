export function won(n: number): string {
  return n.toLocaleString("ko-KR") + "원";
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

/** n개월 전 1일의 ISO 날짜. */
export function monthsAgoStart(months: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - months);
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}
