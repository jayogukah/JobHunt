import { useMemo, useState } from "react";
import Header from "./components/Header";
import RunSummary from "./components/RunSummary";
import FilterBar from "./components/FilterBar";
import JobCard from "./components/JobCard";
import JobDetail from "./components/JobDetail";
import { filterJobs, useJobs } from "./hooks/useJobs";

const INITIAL_FILTERS = { minFit: 0, sponsorship: "all", remoteOnly: false };

export default function App() {
  const { jobs, meta, loading, error, reload } = useJobs();
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [selected, setSelected] = useState(null);

  const visible = useMemo(() => filterJobs(jobs, filters), [jobs, filters]);

  if (selected) {
    // Sync the detail view's job back into the latest jobs list so a refresh
    // while viewing doesn't show stale data.
    const fresh = jobs.find((j) => j.source_id === selected.source_id && j.source === selected.source) || selected;
    return <JobDetail job={fresh} onBack={() => setSelected(null)} />;
  }

  return (
    <div className="min-h-[100dvh] bg-slate-900 text-white">
      <Header runDate={meta?.run_date} onRefresh={reload} refreshing={loading} />
      <RunSummary meta={meta} jobCount={jobs.length} />
      <FilterBar filters={filters} setFilters={setFilters} />

      {loading && <Spinner />}
      {error && !loading && <ErrorBlock message={error} onRetry={reload} />}

      {!loading && !error && (
        <main className="px-4 py-3 max-w-xl mx-auto">
          <p className="text-xs text-slate-500 mb-2">
            Showing {visible.length} of {jobs.length} scored jobs
          </p>
          {visible.length === 0 ? (
            <div className="rounded-xl border border-slate-800 bg-slate-800/40 p-6 text-center text-sm text-slate-400">
              No jobs match your filters.
            </div>
          ) : (
            <ul className="space-y-2">
              {visible.map((job, i) => (
                <li key={`${job.source}:${job.source_id}:${i}`}>
                  <JobCard job={job} index={i} onOpen={() => setSelected(job)} />
                </li>
              ))}
            </ul>
          )}
        </main>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="h-8 w-8 rounded-full border-2 border-slate-700 border-t-slate-300 animate-spin" />
    </div>
  );
}

function ErrorBlock({ message, onRetry }) {
  return (
    <div className="px-4 py-8 max-w-xl mx-auto">
      <div className="rounded-xl border border-rose-800 bg-rose-500/10 p-4 text-sm text-rose-200">
        <p className="font-semibold">Something went wrong fetching jobs.</p>
        <p className="mt-1 text-rose-300/90 break-words">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center rounded-md bg-white/90 text-slate-900 px-3 py-1.5 text-xs font-semibold hover:bg-white"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
