import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";
export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  globalIgnores([
    ".next/**",
    ".agents/**",
    "playwright-report/**",
    "test-results/**",
    "src/lib/openapi.generated.ts",
    "next-env.d.ts",
  ]),
]);
