import { expect, it } from "vitest";
import { backendOrigin, routeAllowed } from "@/lib/proxy";
it.each([
  "https://127.0.0.1:8000",
  "http://example.com",
  "http://127.0.0.1.example.com",
  "http://user:secret@127.0.0.1:8000",
  "http://127.0.0.1:8000/path",
  "http://127.0.0.1?x=1",
])("rejects unsafe backend configuration %s", (value) =>
  expect(() => backendOrigin(value)).toThrow(),
);
it("allows only credential-free local origins", () => {
  expect(backendOrigin("http://127.0.0.1:58000")).toBe(
    "http://127.0.0.1:58000",
  );
  expect(backendOrigin("http://[::1]:8000")).toBe("http://[::1]:8000");
});
it("exposes a narrow backend route allowlist", () => {
  expect(routeAllowed("GET", "health")).toBe(true);
  expect(routeAllowed("GET", "audit-events")).toBe(true);
  expect(
    routeAllowed(
      "POST",
      "loans/12345678-1234-1234-1234-123456789012/repayments",
    ),
  ).toBe(true);
  expect(routeAllowed("GET", "../health")).toBe(false);
  expect(routeAllowed("GET", "openapi.json")).toBe(false);
  expect(routeAllowed("DELETE", "borrowers")).toBe(false);
});
