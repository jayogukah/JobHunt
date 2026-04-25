import {
  avatarColor,
  companyInitials,
  formatSalary,
  formatScore,
  postedAge,
  scoreColor,
  sponsorshipBadge,
} from "../utils/format";

export default function JobCard({ job, onOpen, index }) {
  const fit = job.fit_score ?? job.heuristic_score ?? 0;
  const sc = scoreColor(fit);
  const sp = sponsorshipBadge(job.sponsorship_likely);
  const salary = formatSalary(job.salary_min, job.salary_max, job.currency);
  const age = postedAge(job.posted_at);

  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full text-left rounded-xl bg-slate-800 border border-slate-700/70 p-3 hover:border-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-500 transition-colors fade-in"
      style={{ animationDelay: `${Math.min(index, 20) * 15}ms` }}
    >
      <div className="flex gap-3">
        <div
          className={`w-11 h-11 rounded-lg flex items-center justify-center text-sm font-semibold shrink-0 ${avatarColor(
            job.company + job.source,
          )}`}
          aria-hidden
        >
          {companyInitials(job.company)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2 min-w-0">
            <span className="font-semibold truncate">{job.company || "Unknown"}</span>
            <span className="text-slate-300 text-sm truncate">· {job.title}</span>
          </div>
          <div className="mt-0.5 text-xs text-slate-400 flex items-center gap-2 truncate">
            <span className="truncate">{job.location || "location unspecified"}</span>
            {job.remote && (
              <span className="shrink-0 inline-flex items-center rounded-full border border-emerald-700 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300">
                Remote
              </span>
            )}
          </div>

          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-slate-700 overflow-hidden">
              <div
                className={`h-full ${sc.bg}`}
                style={{ width: `${Math.max(0, Math.min(1, fit)) * 100}%` }}
              />
            </div>
            <span className={`text-xs font-semibold ${sc.text}`}>{formatScore(fit)}</span>
            <span
              className={`shrink-0 inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] ${sp.cls}`}
            >
              {sp.label}
            </span>
          </div>

          {job.why_apply && (
            <p className="mt-2 text-sm text-slate-300 line-clamp-2">{job.why_apply}</p>
          )}

          {(salary || age) && (
            <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
              <span>{salary || ""}</span>
              <span>{age}</span>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
