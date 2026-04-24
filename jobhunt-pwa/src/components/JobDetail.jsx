import { useState } from "react";
import { resolveCvUrl } from "../config";
import {
  formatSalary,
  postedAge,
  scoreColor,
  sponsorshipBadge,
} from "../utils/format";

function Section({ title, items, defaultOpen = false, itemClass = "" }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!items || items.length === 0) return null;
  return (
    <section className="border-t border-slate-800 py-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between text-left"
      >
        <span className="text-sm font-semibold text-slate-200">{title}</span>
        <span className="text-xs text-slate-500">{open ? "hide" : `${items.length} item${items.length === 1 ? "" : "s"}`}</span>
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5 text-sm text-slate-300 list-disc pl-5">
          {items.map((b, i) => (
            <li key={i} className={itemClass}>{b}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function JobDetail({ job, onBack }) {
  const fit = job.fit_score ?? job.heuristic_score ?? 0;
  const sc = scoreColor(fit);
  const sp = sponsorshipBadge(job.sponsorship_likely);
  const salary = formatSalary(job.salary_min, job.salary_max, job.currency);
  const age = postedAge(job.posted_at);
  const cvUrl = resolveCvUrl(job.cv_path);

  return (
    <div className="min-h-[100dvh] bg-slate-900">
      <header className="sticky top-0 z-20 bg-slate-900/95 backdrop-blur border-b border-slate-800">
        <div className="px-4 py-3 flex items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            aria-label="Back"
            className="p-2 -ml-2 rounded-full text-slate-300 hover:text-white hover:bg-slate-800"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          </button>
          <div className="min-w-0">
            <div className="text-xs text-slate-400 truncate">{job.company}</div>
            <div className="font-semibold truncate">{job.title}</div>
          </div>
        </div>
      </header>

      <main className="px-4 pb-28 pt-3 max-w-xl mx-auto">
        <div className="flex flex-wrap gap-2 text-xs">
          {job.location && (
            <span className="inline-flex items-center rounded-full bg-slate-800 border border-slate-700 px-2 py-0.5 text-slate-300">
              {job.location}
            </span>
          )}
          {job.remote && (
            <span className="inline-flex items-center rounded-full border border-emerald-700 bg-emerald-500/10 px-2 py-0.5 text-emerald-300">
              Remote
            </span>
          )}
          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 ${sp.cls}`}>
            {sp.label}
          </span>
          {age && (
            <span className="inline-flex items-center rounded-full bg-slate-800 border border-slate-700 px-2 py-0.5 text-slate-400">
              {age}
            </span>
          )}
          {salary && (
            <span className="inline-flex items-center rounded-full bg-slate-800 border border-slate-700 px-2 py-0.5 text-slate-300">
              {salary}
            </span>
          )}
        </div>

        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-800/50 p-4">
          <div className="flex items-baseline justify-between">
            <span className="text-xs uppercase tracking-wider text-slate-500">Fit score</span>
            <span className={`text-3xl font-bold ${sc.text}`}>{fit.toFixed(2)}</span>
          </div>
          <div className="mt-2 h-2 rounded-full bg-slate-700 overflow-hidden">
            <div className={`h-full ${sc.bg}`} style={{ width: `${Math.max(0, Math.min(1, fit)) * 100}%` }} />
          </div>
        </div>

        {job.why_apply && (
          <section className="mt-4">
            <h2 className="text-xs uppercase tracking-wider text-slate-500 mb-1">Why apply</h2>
            <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{job.why_apply}</p>
          </section>
        )}

        <Section title="Strengths" items={job.strengths} defaultOpen />
        <Section title="Gaps" items={job.gaps} />
        <Section title="Red flags" items={job.red_flags} itemClass="text-amber-300" />

        {job.why_skip && (
          <section className="border-t border-slate-800 py-3">
            <h2 className="text-sm font-semibold text-slate-200">Why the scorer flagged this</h2>
            <p className="mt-1 text-sm text-slate-300">{job.why_skip}</p>
          </section>
        )}

        <div className="mt-4 text-[11px] text-slate-500">
          Source: {job.source}
          {job.source_id ? ` · ${job.source_id}` : ""}
          {job.run_date ? ` · run ${job.run_date}` : ""}
        </div>
      </main>

      <div className="fixed bottom-0 inset-x-0 bg-slate-900/95 backdrop-blur border-t border-slate-800 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <div className="max-w-xl mx-auto px-4 pt-3 space-y-2">
          {cvUrl && (
            <a
              href={cvUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="block text-center w-full rounded-lg border border-slate-600 bg-slate-800 py-3 text-sm font-semibold text-slate-100 hover:bg-slate-700"
            >
              View tailored CV
            </a>
          )}
          {job.apply_url && (
            <a
              href={job.apply_url}
              target="_blank"
              rel="noreferrer noopener"
              className="block text-center w-full rounded-lg bg-white py-3 text-sm font-semibold text-slate-900 hover:bg-slate-200"
            >
              Apply now
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
