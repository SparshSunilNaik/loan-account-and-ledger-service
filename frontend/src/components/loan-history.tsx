"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStudio } from "@/lib/session";
import type { AuditEvent } from "@/lib/types";
import { CopyId, ErrorState, Json, Loading, utc } from "./ui";
export function LoanHistory({
  loanId,
  relatedIds,
  onSelect,
}: {
  loanId: string;
  relatedIds: string[];
  onSelect?: (event: AuditEvent) => void;
}) {
  const { actor } = useStudio();
  const q = useQuery({
    queryKey: ["account-history", loanId, actor, relatedIds.join(",")],
    queryFn: async () => {
      const matches: AuditEvent[] = [];
      let count = 0,
        complete = false;
      for (let page = 0; page < 10; page++) {
        const rows = await api.audit(actor, page * 500, 500);
        count += rows.length;
        matches.push(
          ...rows.filter(
            (e) =>
              e.entity_id === loanId ||
              e.details.loan_id === loanId ||
              relatedIds.includes(e.entity_id ?? "") ||
              relatedIds.includes(String(e.details.journal_id)),
          ),
        );
        if (rows.length < 500) {
          complete = true;
          break;
        }
      }
      return { matches, count, complete };
    },
  });
  if (q.isPending) return <Loading label="Finding this loan’s audit events…" />;
  if (q.isError)
    return (
      <>
        <p className="page-note">
          Loan history requires demo-manager or demo-auditor. Change the demo
          identity above.
        </p>
        <ErrorState error={q.error} />
      </>
    );
  return (
    <>
      <p className="page-note">
        {q.data.matches.length} matching events from {q.data.count} audit
        records scanned.{" "}
        {q.data.complete
          ? "End of available history reached."
          : "Scan capped at 5,000 records; use Activity to continue global pagination."}
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Action</th>
              <th>When (UTC)</th>
              <th>Actor</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {q.data.matches.map((e) => (
              <tr key={e.id}>
                <td>
                  {onSelect ? (
                    <button
                      className="record-select"
                      onClick={() => onSelect(e)}
                    >
                      {e.action}
                    </button>
                  ) : (
                    e.action
                  )}
                </td>
                <td>{utc(e.created_at)}</td>
                <td>
                  <CopyId value={e.actor_user_id} short />
                </td>
                <td>
                  {onSelect ? (
                    <button className="text-link" onClick={() => onSelect(e)}>
                      Inspect event
                    </button>
                  ) : (
                    <Json value={e.details} label="Event metadata" />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
