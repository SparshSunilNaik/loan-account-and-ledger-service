"use client";
import { useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { UUID_PATTERN, session, useStudio } from "@/lib/session";
import { Badge, ErrorState, Loading } from "./ui";
export function LoanContext({ id }: { id: string }) {
  const { actor } = useStudio();
  const q = useQuery({
    queryKey: ["loan", id, actor],
    queryFn: () => api.loan(id, actor),
    enabled: UUID_PATTERN.test(id),
  });
  const b = useQuery({
    queryKey: ["borrower", q.data?.borrower_id, actor],
    queryFn: () => api.borrower(q.data!.borrower_id, actor),
    enabled: !!q.data,
  });
  useEffect(() => {
    if (q.data) session.remember(id, q.data.external_reference);
  }, [id, q.data]);
  if (!UUID_PATTERN.test(id)) return null;
  if (q.isPending) return <Loading label="Reading working account…" />;
  if (q.isError) return <ErrorState error={q.error} />;
  return (
    <div className="loan-context">
      <div className="borrower-avatar">
        {b.data?.full_name.slice(0, 1) ?? "…"}
      </div>
      <div>
        <h2>{b.data?.full_name ?? "Reading borrower…"}</h2>
        <span>{q.data.external_reference}</span>
      </div>
      <Badge tone={q.data.status === "disbursed" ? "good" : "neutral"}>
        {q.data.status === "originated"
          ? "Awaiting disbursement"
          : q.data.status}
      </Badge>
      <Link href={`/loans/${id}`} className="text-link">
        Open account
      </Link>
    </div>
  );
}
