import type { components } from "./openapi.generated";
export type Borrower = components["schemas"]["BorrowerRead"];
export type BorrowerInput = components["schemas"]["BorrowerCreate"];
export type Loan = components["schemas"]["LoanRead"];
export type LoanInput = components["schemas"]["LoanCreate"];
export type Product = components["schemas"]["ProductRead"];
export type ScheduleRow = components["schemas"]["ScheduleRead"];
export type RepaymentInput = components["schemas"]["RepaymentCreate"];
export const actors = ["demo-officer", "demo-manager", "demo-auditor"] as const;
export type Actor = (typeof actors)[number];
// These response routes have generic OpenAPI schemas. Fields below mirror the existing
// FastAPI route serializers; they are not invented additions to the backend contract.
export interface Balance {
  loan_id: string;
  currency: "INR";
  principal_receivable_paise: number;
  interest_receivable_paise: number;
  penalty_receivable_paise: number;
  total_posted_receivables_paise: number;
}
export interface Allocation {
  schedule_id: string;
  component: string;
  amount_paise: number;
}
export interface Receipt {
  id: string;
  loan_id: string;
  journal_id: string;
  amount_paise: number;
  source: string;
  external_event_id: string;
  occurred_at: string;
  received_at: string;
  business_date: string;
  status: string;
  reversal_journal_id?: string | null;
  allocations: Allocation[];
}
export interface Entry {
  id: string;
  account: string;
  direction: "debit" | "credit";
  amount_paise: number;
  schedule_id: string | null;
  receivable_origin_id: string | null;
}
export interface Journal {
  id: string;
  kind: string;
  status: string;
  business_date: string;
  effective_at: string;
  posted_at: string;
  repayment_id: string | null;
  reversal_of_id: string | null;
  description: string;
  entries: Entry[];
}
export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  correlation_id: string | null;
  created_at: string;
  details: Record<string, unknown>;
}
export interface Disbursement {
  loan_id: string;
  journal_id: string;
  status: string;
}
