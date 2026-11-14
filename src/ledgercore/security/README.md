# Local demo authentication only

`DEMO_AUTH_ENABLED=true` enables database-backed `X-Demo-User` subjects:
`demo-officer`, `demo-manager`, `demo-auditor`. Roles come from active database users,
never from headers. Missing/unknown/inactive subjects and unauthorized actions return 403.
Disabled demo authentication returns 503 on protected endpoints. Public endpoints are
health, Swagger and OpenAPI. There are no real credentials or authentication tokens.

This is impersonation for local development, not proof of identity. Never expose it to
untrusted clients. Production identity verification and tenant/borrower scoping remain
unimplemented. All three roles can read all loans in this demo. Managers and auditors can
read audit history; only officers/managers can originate and receive repayments; only
managers can disburse or reverse supported repayment journals. Denials are recorded in a
separate small authorization transaction without request payloads or unrecognized subject
values. Successful mutations carry the actor and correlation in the financial transaction.
