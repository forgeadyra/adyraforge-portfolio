"use client";

import { useState } from "react";

import { Alert, Empty, errorText, formatDate, formatMoney } from "@/components/ui";
import { endpoints, type Invoice } from "@/lib/api";
import { useApi } from "@/lib/use-api";

const STATUS: Record<Invoice["status"], string> = {
  sent: "Due",
  paid: "Paid",
  overdue: "Overdue",
  void: "Void",
};

export function InvoiceList({ project }: { project?: number }) {
  const { data, error } = useApi(() => endpoints.invoices(project), `invoices-${project ?? "all"}`);
  const [downloadError, setDownloadError] = useState("");

  async function download(id: number) {
    setDownloadError("");
    try {
      const { url } = await endpoints.invoiceDownload(id);
      window.location.assign(url);
    } catch (e) {
      setDownloadError(errorText(e));
    }
  }

  if (error) return <Alert tone="error">{errorText(error)}</Alert>;
  if (!data) return <p aria-busy="true">Loading…</p>;
  if (data.results.length === 0) return <Empty>No invoices yet.</Empty>;

  return (
    <>
      {downloadError && <Alert tone="error">{downloadError}</Alert>}
      <div className="mt-4 overflow-x-auto rounded-lg border border-ink/10">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Invoices</caption>
          <thead className="bg-surface text-muted">
            <tr>
              <th scope="col" className="p-3">
                Invoice
              </th>
              <th scope="col" className="p-3">
                Amount
              </th>
              <th scope="col" className="p-3">
                Status
              </th>
              <th scope="col" className="p-3">
                Due
              </th>
              <th scope="col" className="p-3">
                <span className="sr-only">PDF</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10">
            {data.results.map((inv) => (
              <tr key={inv.id}>
                <th scope="row" className="p-3 font-medium">
                  {inv.number}
                </th>
                <td className="p-3">{formatMoney(inv.amount, inv.currency)}</td>
                <td className={`p-3 ${inv.status === "overdue" ? "text-red-200" : ""}`}>
                  {STATUS[inv.status]}
                </td>
                <td className="p-3">{formatDate(inv.due_date)}</td>
                <td className="p-3 text-right">
                  {inv.has_pdf && (
                    <button
                      type="button"
                      onClick={() => download(inv.id)}
                      className="text-accent underline"
                    >
                      PDF<span className="sr-only"> for invoice {inv.number}</span>
                    </button>
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
