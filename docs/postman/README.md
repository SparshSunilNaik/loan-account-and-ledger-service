# Postman assets

Import `ledgercore.postman_collection.json` and `local.postman_environment.json`, select
the local environment and run the collection in order against a fresh demo database.
Variables include base URL, all three demo subjects, borrower/loan/product/journal IDs,
repayment/reversal IDs, idempotency keys and explicit business dates. Initial ID values
are intentionally empty; the scripts capture actual API responses. No credentials/tokens
are shipped. The first request initializes unique run references and keys.

The collection covers all 14 OpenAPI operations plus Swagger, ReDoc, OpenAPI export and
Swagger redirect support. Expected negative cases are assertions, not collection failures.
Audit pagination defaults to the first 500 records; adjust auditOffset on an older database.
The collection also verifies one receipt after retries, immutable schedules, balanced
journals using BigInt, correct allocation and reversal restoration.

Regenerate from a running application:

```sh
uv run python scripts/export_api_assets.py --base-url http://127.0.0.1:8000
uv run --with openapi-spec-validator==0.7.2 python scripts/verify_submission.py --base-url http://127.0.0.1:8000
```

`docs/openapi.json` is the running endpoint's JSON, not a hand-edited approximation. It is
OpenAPI 3.1.0. Some financial responses retain generic response schemas; the collection
provides executable examples and assertions without claiming tighter schemas than the app.

The vendored `collection.schema.json` is the official Postman Collection v2.1 schema:
https://schema.getpostman.com/json/collection/v2.1.0/collection.json
Downloaded November 14, 2026. `SCHEMA_LICENSE` preserves the Apache 2.0 license from the
Postman collection-format-docs repository. [Schema documentation](https://schema.postman.com/json/collection/v2.1.0/docs/index.html).
[Newman usage](https://learning.postman.com/docs/reference/newman-cli/installing-running-newman).
Validation uses the vendored schema locally; execution uses Newman 6.2.1, not a paid API.
