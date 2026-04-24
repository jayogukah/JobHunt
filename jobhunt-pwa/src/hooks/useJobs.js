import { useCallback, useEffect, useState } from "react";
import { JOBS_URL, META_URL } from "../config";

async function fetchJson(url) {
  // Cache-bust so the browser does not serve a stale raw.githubusercontent
  // response when the repo has been updated in the last few minutes.
  const sep = url.includes("?") ? "&" : "?";
  const res = await fetch(`${url}${sep}_t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} (${url})`);
  return res.json();
}

export function useJobs() {
  const [jobs, setJobs] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch both in parallel; meta is allowed to 404 for runs that
      // predate the meta.json writer.
      const [jobsRes, metaRes] = await Promise.allSettled([
        fetchJson(JOBS_URL),
        fetchJson(META_URL),
      ]);
      if (jobsRes.status === "rejected") throw jobsRes.reason;
      const rawJobs = Array.isArray(jobsRes.value) ? jobsRes.value : [];
      setJobs(rawJobs.filter(Boolean));
      setMeta(metaRes.status === "fulfilled" ? metaRes.value : null);
    } catch (e) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return { jobs, meta, loading, error, reload: load };
}

export function filterJobs(jobs, { minFit, sponsorship, remoteOnly }) {
  return jobs
    .filter((j) => {
      const fit = j.fit_score ?? j.heuristic_score ?? 0;
      if (minFit > 0 && fit < minFit) return false;
      if (sponsorship === "yes" && (j.sponsorship_likely || "").toLowerCase() !== "yes") return false;
      if (sponsorship === "unclear" && (j.sponsorship_likely || "").toLowerCase() === "no") return false;
      if (remoteOnly && j.remote !== true) return false;
      return true;
    })
    .sort((a, b) => (b.fit_score ?? b.heuristic_score ?? 0) - (a.fit_score ?? a.heuristic_score ?? 0));
}
