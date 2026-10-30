/** Format an amount in US dollars, such as 1234.5 as "$1,234.50". */
export function formatMoney(amount: number): string {
  return amount.toLocaleString("en-US", { style: "currency", currency: "USD" });
}
