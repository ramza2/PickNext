/**
 * Safe date formatting for API ISO-8601 strings.
 * Returns empty string on invalid input (no throw).
 */
export function formatDate(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  try {
    return date.toLocaleDateString("ko-KR");
  } catch {
    return "";
  }
}
