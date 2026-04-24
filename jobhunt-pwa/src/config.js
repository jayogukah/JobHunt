// Change this to your GitHub username / repo / branch if you fork.
const GH_USER = "jayogukah";
const GH_REPO = "JobHunt";
const GH_BRANCH = "main";

export const REPORTS_BASE =
  `https://raw.githubusercontent.com/${GH_USER}/${GH_REPO}/${GH_BRANCH}/reports/latest/`;

export const JOBS_URL = `${REPORTS_BASE}jobs.json`;
export const META_URL = `${REPORTS_BASE}meta.json`;

// When a job points at a tailored CV like "tailored/foo.docx", we resolve
// it against REPORTS_BASE so the browser opens a direct raw.githubusercontent
// link that works without auth.
export function resolveCvUrl(cvPath) {
  if (!cvPath) return null;
  if (cvPath.startsWith("http")) return cvPath;
  return REPORTS_BASE + cvPath.replace(/^\//, "");
}
