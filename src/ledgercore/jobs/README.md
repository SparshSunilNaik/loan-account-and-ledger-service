# No scheduled execution in Phase 2

The independently callable `recognize_scheduled_interest` service accepts an explicit
UTC business date and caller-owned Session, locks the loan, and recognizes due contractual
interest once. Repayment invokes it before allocation. No scheduler, overdue accrual,
penalty generation, replay, or synthetic data generator runs. Future jobs must use this
service contract, per-loan locking, and unique schedule/kind/period identities.
