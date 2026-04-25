import { useState } from "react";
import { resolveCvUrl } from "../config";
import {
  formatSalary,
  formatScore,
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
  const aiSummary = (job.ai_summary || "").trim();
  const nextSteps = Array.isArray(job.next_steps)
    ? job.next_steps.filter((s) => s && String(s).trim())
    : [];

  return (
    <div className="min-h-[100dvh] bg-slate-900">
      <header
        className="sticky top-0 z-20 bg-slate-900/95 backdrop-blur border-b border-slate-800"
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
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
        {/* 1. Meta row + 2. Salary row */}
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

        {/* 3. Fit score */}
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-800/50 p-4">
          <div className="flex items-baseline justify-between">
            <span className="text-xs uppercase tracking-wider text-slate-500">Fit score</span>
            <span className={`text-3xl font-bold ${sc.text}`}>{formatScore(fit)}</span>
          </div>
          <div className="mt-2 h-2 rounded-full bg-slate-700 overflow-hidden">
            <div className={`h-full ${sc.bg}`} style={{ width: `${Math.max(0, Math.min(1, fit)) * 100}%` }} />
          </div>
        </div>

        {/* 4. AI Summary (new) */}
        {aiSummary && (
          <section className="mt-4">
            <h2 className="text-xs uppercase tracking-wider text-slate-500 mb-1">What this role actually is</h2>
            <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{aiSummary}</p>
          </section>
        )}

        {/* 5. Why apply (relabeled) */}
        {job.why_apply && (
          <section className="mt-4">
            <h2 className="text-xs uppercase tracking-wider text-slate-500 mb-1">Why it fits your background</h2>
            <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{job.why_apply}</p>
          </section>
        )}

        {/* 6. Next steps (new) — actionable, amber accent */}
        {nextSteps.length > 0 && (
          <section className="mt-4 rounded-lg border-l-4 border-amber-400 bg-slate-700/40 p-3">
            <h2 className="text-sm font-semibold text-slate-100">Things to do before applying</h2>
            <ul className="mt-2 space-y-1.5 text-sm text-slate-200 list-disc pl-5">
              {nextSteps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ul>
          </section>
        )}

        {/* 7-9. Collapsible sections */}
        <Section title="Strengths" items={job.strengths} defaultOpen />
        <Section title="Gaps" items={job.gaps} />
        <Section title="Red flags" items={job.red_flags} itemClass="text-amber-300" />

        {/* 10. Source */}
        <div className="mt-4 text-[11px] text-slate-500">
          Source: {job.source}
          {job.source_id ? ` · ${job.source_id}` : ""}
          {job.run_date ? ` · run ${job.run_date}` : ""}
        </div>
      </main>

      {/* 11. Sticky bottom button row */}
      <div
        className="fixed bottom-0 inset-x-0 bg-slate-900/95 backdrop-blur border-t border-slate-800"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <div className="max-w-xl mx-auto px-4 pt-3 pb-3 space-y-2">
          {cvUrl && (
            <a
              href={cvUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="block text-center w-full rounded-lg border border-slate-400 bg-transparent py-3 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Tailor My CV to This Role
            </a>
          )}
          {job.apply_url && (
            <a
              href={job.apply_url}
              target="_blank"
              rel="noreferrer noopener"
              className="block text-center w-full rounded-lg bg-emerald-600 py-3 text-sm font-semibold text-white hover:bg-emerald-500"
            >
              Apply Now
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
