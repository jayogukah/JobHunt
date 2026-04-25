// Small pure helpers. No external deps.

export function postedAge(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const days = Math.max(0, Math.floor((Date.now() - d.getTime()) / 86400000));
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? "1 month ago" : `${months} months ago`;
}

export function scoreColor(score) {
  if (score == null) return { bg: "bg-slate-600", text: "text-slate-300" };
  if (score >= 0.8) return { bg: "bg-emerald-500", text: "text-emerald-400" };
  if (score >= 0.6) return { bg: "bg-amber-500", text: "text-amber-400" };
  return { bg: "bg-rose-500", text: "text-rose-400" };
}

// Whole-number percentage label, used wherever a fit/heuristic score is shown
// to a human. Bar widths (CSS percentage) still multiply the raw 0..1 value
// directly — do not route the bar width through this.
export function formatScore(score) {
  if (score == null) return "N/A";
  return Math.round(score * 100) + "%";
}

export function sponsorshipBadge(value) {
  switch ((value || "").toLowerCase()) {
    case "yes":
      return { label: "Visa OK", cls: "bg-emerald-500/20 text-emerald-300 border-emerald-700" };
    case "no":
      return { label: "No Visa", cls: "bg-rose-500/20 text-rose-300 border-rose-700" };
    default:
      return { label: "Visa unclear", cls: "bg-amber-500/20 text-amber-300 border-amber-700" };
  }
}

export function formatSalary(min, max, currency) {
  if (min == null && max == null) return null;
  const fmt = (n) => {
    if (n == null) return "";
    if (n >= 1000) return `${Math.round(n / 1000)}k`;
    return `${Math.round(n)}`;
  };
  const cur = currency ? `${currency} ` : "";
  if (min != null && max != null) return `${cur}${fmt(min)}–${fmt(max)}`;
  if (min != null) return `${cur}from ${fmt(min)}`;
  return `${cur}up to ${fmt(max)}`;
}

// Deterministic color for a source-derived company avatar background.
const PALETTE = [
  "bg-sky-700",
  "bg-indigo-700",
  "bg-fuchsia-700",
  "bg-emerald-700",
  "bg-amber-700",
  "bg-rose-700",
  "bg-teal-700",
  "bg-violet-700",
];
export function avatarColor(seed) {
  if (!seed) return PALETTE[0];
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export function companyInitials(name) {
  if (!name) return "??";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}
