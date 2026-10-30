/** Amounts are whole cents inside the dashboard, and two-decimal strings on the wire. */

/** Read a wire amount such as "1234.50" as whole cents. */
export function parseCents(amount: string): number {
  const [dollars = "0", cents = ""] = amount.split(".");
  return Number(dollars) * 100 + Number(cents.padEnd(2, "0"));
}

/** Write whole cents as a wire amount, such as 123450 as "1234.50". */
export function toWireAmount(cents: number): string {
  const rest = String(cents % 100).padStart(2, "0");
  return `${String(Math.trunc(cents / 100))}.${rest}`;
}

/** Format whole cents for people, such as 123450 as "$1,234.50". */
export function formatMoney(cents: number): string {
  const dollars = Math.trunc(cents / 100).toLocaleString("en-US");
  return `$${dollars}.${String(cents % 100).padStart(2, "0")}`;
}
