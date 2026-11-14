import { validateMonetaryIntegers } from "./money";
import type {
  Actor,
  AuditEvent,
  Balance,
  Borrower,
  BorrowerInput,
  Disbursement,
  Journal,
  Loan,
  LoanInput,
  Product,
  Receipt,
  RepaymentInput,
  ScheduleRow,
} from "./types";
export interface Reply<T = unknown> {
  status: number | null;
  ok: boolean;
  body: T;
  rawText: string;
  origin: "backend" | "proxy" | "browser";
}
export function errorMessage(body: unknown): string {
  if (typeof body === "string") return body;
  if (body && typeof body === "object" && "detail" in body) {
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
      return detail
        .map(
          (e) =>
            `${Array.isArray(e.loc) ? e.loc.join(" → ") : "Input"}: ${e.msg}`,
        )
        .join("; ");
  }
  return "The request could not be completed. Inspect the actual response below.";
}
export class ApiFailure extends Error {
  constructor(public reply: Reply) {
    super(errorMessage(reply.body));
    this.name = "ApiFailure";
  }
}
export async function request<T>(
  path: string,
  actor: Actor,
  options: { method?: "GET" | "POST"; body?: unknown; key?: string } = {},
): Promise<Reply<T>> {
  try {
    const response = await fetch(`/api/backend${path}`, {
      method: options.method ?? "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(22000),
      headers: {
        "X-Demo-User": actor,
        ...(options.body === undefined
          ? {}
          : { "Content-Type": "application/json" }),
        ...(options.key ? { "Idempotency-Key": options.key } : {}),
      },
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const rawText = await response.text();
    let body: unknown;
    try {
      body = JSON.parse(rawText);
    } catch {
      body = rawText;
    }
    if (response.ok) validateMonetaryIntegers(body);
    return {
      status: response.status,
      ok: response.ok,
      body: body as T,
      rawText,
      origin:
        body && typeof body === "object" && "studio_proxy" in body
          ? "proxy"
          : "backend",
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Network failure";
    const body = {
      detail: `${detail}. No trustworthy HTTP result is available. A mutation may have committed; inspect receipts and retry its identical key.`,
    };
    return {
      status: null,
      ok: false,
      body: body as T,
      rawText: JSON.stringify(body),
      origin: "browser",
    };
  }
}
export async function get<T>(path: string, actor: Actor): Promise<T> {
  const result = await request<T>(path, actor);
  if (!result.ok) throw new ApiFailure(result);
  return result.body;
}
export const api = {
  health: (actor: Actor) =>
    get<{ status: string; database: string }>("/health", actor),
  products: (actor: Actor) => get<Product[]>("/loan-products", actor),
  borrower: (id: string, actor: Actor) =>
    get<Borrower>(`/borrowers/${id}`, actor),
  createBorrower: (body: BorrowerInput, actor: Actor) =>
    request<Borrower>("/borrowers", actor, { method: "POST", body }),
  createLoan: (body: LoanInput, actor: Actor) =>
    request<Loan>("/loans", actor, { method: "POST", body }),
  loan: (id: string, actor: Actor) => get<Loan>(`/loans/${id}`, actor),
  schedule: (id: string, actor: Actor) =>
    get<ScheduleRow[]>(`/loans/${id}/schedule`, actor),
  balance: (id: string, actor: Actor) =>
    get<Balance>(`/loans/${id}/balance`, actor),
  receipts: (id: string, actor: Actor) =>
    get<Receipt[]>(`/loans/${id}/repayments`, actor),
  ledger: (id: string, actor: Actor) =>
    get<Journal[]>(`/loans/${id}/ledger`, actor),
  audit: (actor: Actor, offset = 0, limit = 50) =>
    get<AuditEvent[]>(`/audit-events?limit=${limit}&offset=${offset}`, actor),
  disburse: (id: string, date: string, actor: Actor) =>
    request<Disbursement>(`/loans/${id}/disburse`, actor, {
      method: "POST",
      body: { business_date: date },
    }),
  repay: (id: string, body: RepaymentInput, key: string, actor: Actor) =>
    request<Receipt>(`/loans/${id}/repayments`, actor, {
      method: "POST",
      body,
      key,
    }),
};
export interface Snapshot {
  balance: Balance;
  receipts: Receipt[];
  ledger: Journal[];
}
export async function snapshot(id: string, actor: Actor): Promise<Snapshot> {
  const [balance, receipts, ledger] = await Promise.all([
    api.balance(id, actor),
    api.receipts(id, actor),
    api.ledger(id, actor),
  ]);
  return { balance, receipts, ledger };
}
export function receiptEffect(
  reply: Reply,
  before?: Snapshot,
  after?: Snapshot,
): string {
  if (!before || !after)
    return "Effect unverified — refresh authoritative records before deciding what happened.";
  if (
    !reply.ok ||
    reply.status !== 201 ||
    !reply.body ||
    typeof reply.body !== "object" ||
    !("id" in reply.body) ||
    !("journal_id" in reply.body)
  )
    return "No successful receipt response. Before/after observations are shown; status alone does not prove financial effects.";
  const id = reply.body.id,
    journal = reply.body.journal_id;
  const priorReceipt = before.receipts.some((r) => r.id === id),
    currentReceipt = after.receipts.some((r) => r.id === id);
  const priorJournal = before.ledger.some((j) => j.id === journal),
    currentJournal = after.ledger.some((j) => j.id === journal);
  if (priorReceipt && currentReceipt && priorJournal && currentJournal)
    return "Existing receipt and journal verified — original response reused.";
  if (!priorReceipt && currentReceipt && !priorJournal && currentJournal)
    return "New receipt and journal observed in backend records.";
  return "Identifiers could not be reconciled across observations — inspect receipts and ledger.";
}
export interface Attempt {
  loanId: string;
  body: RepaymentInput;
  key: string;
  actor: Actor;
}
export interface Observation {
  name: string;
  attempt: Attempt;
  reply: Reply;
  before?: Snapshot;
  after?: Snapshot;
  verificationError?: string;
}
export async function observeRepayment(
  attempt: Attempt,
  name: string,
): Promise<Observation> {
  const before = await snapshot(attempt.loanId, attempt.actor);
  const reply = await api.repay(
    attempt.loanId,
    attempt.body,
    attempt.key,
    attempt.actor,
  );
  try {
    return {
      name,
      attempt,
      reply,
      before,
      after: await snapshot(attempt.loanId, attempt.actor),
    };
  } catch (error) {
    return {
      name,
      attempt,
      reply,
      before,
      verificationError:
        error instanceof Error ? error.message : "After-state unavailable",
    };
  }
}
