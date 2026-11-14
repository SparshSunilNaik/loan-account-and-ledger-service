const UUID =
  "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const routes: Record<string, RegExp[]> = {
  GET: [
    /^health$/,
    /^loan-products$/,
    new RegExp(`^borrowers/${UUID}$`),
    new RegExp(`^loans/${UUID}(?:/(?:schedule|balance|ledger|repayments))?$`),
    /^audit-events$/,
  ],
  POST: [
    /^borrowers$/,
    /^loans$/,
    new RegExp(`^loans/${UUID}/(?:disburse|repayments)$`),
  ],
};
export function backendOrigin(
  value = process.env.BACKEND_URL ?? "http://127.0.0.1:8000",
): string {
  const url = new URL(value);
  if (
    url.protocol !== "http:" ||
    !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  )
    throw new Error(
      "BACKEND_URL must be a credential-free loopback HTTP origin with no path or query.",
    );
  return url.origin;
}
export function routeAllowed(method: string, path: string): boolean {
  return (routes[method] ?? []).some((pattern) => pattern.test(path));
}
