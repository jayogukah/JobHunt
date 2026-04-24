import { useState } from "react";

export default function RunSummary({ meta, jobCount }) {
  const [open, setOpen] = useState(false);
  if (!meta) {
    return (
      <div className="px-4 py-2 text-xs text-slate-400 border-b border-slate-800">
        {jobCount} scored jobs
      </div>
    );
  }

  const sources = meta.sources || {};
  const failed = Object.entries(sources).filter(([, s]) => s.status && s.status !== "ok");
  const hasFailures = failed.length > 0;
  const partial = !!meta.partial_reason;

  return (
    <div className="border-b border-slate-800">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-2 text-left text-xs text-slate-300 flex items-center gap-3"
      >
        <span className="truncate">
          {meta.run_date} · {meta.total_fetched ?? 0} fetched ·{" "}
          {meta.total_scored ?? 0} scored · top {meta.top_n ?? 0}
        </span>
        {(hasFailures || partial) && (
          <span
            title={partial ? meta.partial_reason : "Some sources failed"}
            className="shrink-0 inline-flex items-center gap-1 rounded-full border border-amber-700 bg-amber-500/10 px-2 py-0.5 text-amber-300"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r="0.5" fill="currentColor"/></svg>
            {partial ? "partial run" : "source issue"}
          </span>
        )}
        <span className="ml-auto text-slate-500">{open ? "hide" : "details"}</span>
      </button>
      {open && (
        <div className="px-4 pb-3 text-xs text-slate-400 space-y-1">
          {partial && (
            <div className="rounded border border-amber-800 bg-amber-500/10 px-2 py-1 text-amber-200">
              Partial run: {meta.partial_reason}
            </div>
          )}
          <table className="w-full text-left">
            <tbody>
              {Object.entries(sources).map(([name, s]) => (
                <tr key={name} className="border-t border-slate-800/60">
                  <td className="py-1 pr-2 text-slate-300">{name}</td>
                  <td className="py-1 pr-2">{s.count ?? 0}</td>
                  <td className={`py-1 text-right ${s.status === "ok" ? "text-emerald-400" : "text-rose-400"}`}>
                    {s.status || ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
