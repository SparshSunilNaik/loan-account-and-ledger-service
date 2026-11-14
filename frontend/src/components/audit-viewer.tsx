"use client";
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  RefreshCw,
  X,
  LockKeyhole,
} from "lucide-react";
import { api } from "@/lib/api";
import { useStudio } from "@/lib/session";
import type { AuditEvent } from "@/lib/types";
import {
  Button,
  CopyId,
  Empty,
  ErrorState,
  Json,
  Loading,
  PageHeading,
  utc,
} from "./ui";
export function AuditViewer({ embedded = false }: { embedded?: boolean }) {
  const { actor } = useStudio();
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<AuditEvent>();
  const limit = 50;
  const events = useQuery({
    queryKey: ["audit", actor, offset],
    queryFn: () => api.audit(actor, offset, limit),
  });
  return (
    <>
      {!embedded && (
        <PageHeading
          eyebrow="Traceability"
          title="Audit trail"
          action={
            <Button variant="secondary" onClick={() => void events.refetch()}>
              <RefreshCw size={14} />
              Refresh records
            </Button>
          }
        >
          Actor attribution and the evidence behind every operation.
        </PageHeading>
      )}
      <div className="audit-toolbar">
        <div>
          <h2>Event log</h2>
          <span className="muted">Chronological · oldest first</span>
        </div>
        <span className="muted">
          50 per page <span className="toolbar-separator">/</span> Offset{" "}
          {offset}
        </span>
      </div>
      {actor === "demo-officer" && (
        <div className="audit-permission">
          <LockKeyhole size={16} />
          <span>
            Audit history requires a manager or auditor identity. Change the
            demo subject in the top bar.
          </span>
        </div>
      )}
      {events.isPending ? (
        <Loading />
      ) : events.isError ? (
        <ErrorState error={events.error} retry={() => void events.refetch()} />
      ) : !events.data.length ? (
        <Empty title="No events in this page">
          Previous pages may contain records.
        </Empty>
      ) : (
        <div className="table-scroll">
          <table className="audit-table">
            <caption className="sr-only">
              Audit events with action, UTC timestamp, actor, entity and
              correlation identifiers
            </caption>
            <thead>
              <tr>
                <th>Action</th>
                <th>Timestamp · UTC</th>
                <th>Actor</th>
                <th>Entity</th>
                <th>Correlation ID</th>
                <th>
                  <span className="sr-only">Event details</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {events.data.map((e) => (
                <tr key={e.id}>
                  <td>
                    <span className="action-name">
                      <span
                        className={
                          e.action.includes("denied")
                            ? "event-dot denied"
                            : "event-dot"
                        }
                      />
                      {e.action}
                    </span>
                  </td>
                  <td className="nowrap date-cell">{utc(e.created_at)}</td>
                  <td>
                    <CopyId value={e.actor_user_id} short />
                  </td>
                  <td>
                    <span className="entity-label">{e.entity_type}</span>
                    <span className="cell-meta">
                      <CopyId value={e.entity_id} short />
                    </span>
                  </td>
                  <td>
                    <CopyId value={e.correlation_id} short />
                  </td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Inspect audit event ${e.id}`}
                      onClick={() => setSelected(e)}
                    >
                      <ArrowUpRight size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>
          {events.data && !events.isError
            ? `${events.data.length} events returned`
            : `Reading as ${actor}`}{" "}
          <span className="muted">· current page only</span>
        </span>
        <div>
          <Button
            variant="quiet"
            onClick={() => setOffset((v) => Math.max(0, v - limit))}
            disabled={offset === 0 || events.isFetching}
          >
            <ArrowLeft size={14} />
            Previous page
          </Button>
          <Button
            variant="quiet"
            onClick={() => setOffset((v) => v + limit)}
            disabled={
              !events.data ||
              events.data.length < limit ||
              events.isFetching ||
              events.isError
            }
          >
            Next page
            <ArrowRight size={14} />
          </Button>
        </div>
      </div>
      <p className="page-note">
        Financial mutation audits commit with their journals. No server-side
        search or filtering endpoint is available.
      </p>
      <Dialog.Root
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(undefined);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="audit-drawer">
            <div className="drawer-heading">
              <div>
                <Dialog.Title>Event details</Dialog.Title>
                <Dialog.Description>
                  Actual backend record · monetary metadata in paise
                </Dialog.Description>
              </div>
              <Dialog.Close
                className="icon-button"
                aria-label="Close event details"
              >
                <X size={18} />
              </Dialog.Close>
            </div>
            {selected && (
              <>
                <h2>{selected.action}</h2>
                <dl className="drawer-record">
                  {[
                    ["Event ID", selected.id],
                    ["Actor ID", selected.actor_user_id],
                    ["Entity ID", selected.entity_id],
                    ["Correlation ID", selected.correlation_id],
                  ].map(([label, id]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>
                        <CopyId value={id} />
                      </dd>
                    </div>
                  ))}
                  <div>
                    <dt>Timestamp · UTC</dt>
                    <dd>{utc(selected.created_at)}</dd>
                  </div>
                </dl>
                <Json value={selected.details} label="Recorded metadata" open />
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
