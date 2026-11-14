import { backendOrigin, routeAllowed } from "@/lib/proxy";
import { actors } from "@/lib/types";
export const dynamic = "force-dynamic";
function failure(status: number, detail: string) {
  return Response.json(
    { detail, studio_proxy: true },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}
async function proxy(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const route = path.join("/");
  if (!routeAllowed(request.method, route))
    return failure(404, "This route is outside Studio's local API allowlist.");
  const incoming = new URL(request.url);
  let studioOrigin: string;
  try {
    studioOrigin = backendOrigin(
      `http://${request.headers.get("host") ?? incoming.host}`,
    );
  } catch {
    return failure(403, "Studio accepts loopback hosts only.");
  }
  if (
    request.method === "POST" &&
    request.headers.get("origin") &&
    request.headers.get("origin") !== studioOrigin
  )
    return failure(403, "Cross-origin mutation rejected by Studio.");
  const actor = request.headers.get("X-Demo-User");
  if (actor && !(actors as readonly string[]).includes(actor))
    return failure(403, "Select a supported development demo subject.");
  let origin: string;
  try {
    origin = backendOrigin();
  } catch {
    return failure(
      503,
      "Studio backend configuration is invalid. Configure a loopback BACKEND_URL on the Next.js server.",
    );
  }
  const target = new URL(`${origin}/${route}`);
  for (const [key, value] of incoming.searchParams) {
    if (
      route !== "audit-events" ||
      !["limit", "offset"].includes(key) ||
      !/^\d{1,9}$/.test(value)
    )
      return failure(400, "Unsupported proxy query parameter.");
    target.searchParams.set(key, value);
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (actor) headers["X-Demo-User"] = actor;
  const key = request.headers.get("Idempotency-Key");
  if (key) {
    if (!/^[A-Za-z0-9_.:-]{1,200}$/.test(key))
      return failure(
        400,
        "Idempotency key must use 1–200 identifier characters.",
      );
    headers["Idempotency-Key"] = key;
  }
  let body: string | undefined;
  if (request.method === "POST") {
    body = await request.text();
    if (body.length > 32768)
      return failure(413, "Request is too large for the local Studio proxy.");
    headers["Content-Type"] = "application/json";
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(15000),
    });
    const content = await upstream.text();
    return new Response(content, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
        ...(upstream.headers.get("X-Correlation-ID")
          ? { "X-Correlation-ID": upstream.headers.get("X-Correlation-ID")! }
          : {}),
      },
    });
  } catch (error) {
    const timeout =
      error instanceof Error &&
      ["TimeoutError", "AbortError"].includes(error.name);
    return failure(
      timeout ? 504 : 503,
      timeout
        ? "Local backend timed out. Mutation outcome may be unknown; inspect records, then retry the identical idempotency key."
        : "Local FastAPI backend is unavailable. Check BACKEND_URL and that PostgreSQL and FastAPI are running. A sent mutation's outcome must be verified before retrying.",
    );
  }
}
export const GET = proxy;
export const POST = proxy;
