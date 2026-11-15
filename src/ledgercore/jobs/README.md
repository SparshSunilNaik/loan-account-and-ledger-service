# Explicit dated accrual jobs

`uv run ledgercore-accrue --business-date YYYY-MM-DD --catch-up` recognizes contractual
interest once and evaluates every missing eligible overdue day. It charges 0.0005 of
historical opening unpaid scheduled principal, rounds daily half-up, and persists zero
identities without journals. Each loan owns one atomic transaction and the same row lock
as financial APIs. Failures roll back that loan and cause a nonzero CLI exit; rerun resumes.

No resident scheduler is required. README provides a cron-compatible command and full
local replay/demo commands. The independent HTTP replay fixes job-before-delivery ordering;
late jobs never retroactively rewrite existing receipt allocations.
