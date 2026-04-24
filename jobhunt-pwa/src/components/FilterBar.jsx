const FIT_OPTIONS = [
  { label: "All", value: 0 },
  { label: "0.6+", value: 0.6 },
  { label: "0.7+", value: 0.7 },
  { label: "0.8+", value: 0.8 },
];

const SPONSOR_OPTIONS = [
  { label: "All", value: "all" },
  { label: "Yes", value: "yes" },
  { label: "Unclear", value: "unclear" },
];

function Segmented({ options, value, onChange, label }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">{label}</span>
      <div className="inline-flex rounded-lg bg-slate-800 p-0.5 text-xs">
        {options.map((opt) => {
          const active = value === opt.value;
          return (
            <button
              key={String(opt.value)}
              type="button"
              onClick={() => onChange(opt.value)}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                active
                  ? "bg-slate-700 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function FilterBar({ filters, setFilters }) {
  return (
    <div className="px-4 py-3 flex flex-wrap items-end gap-4 border-b border-slate-800 bg-slate-900/60">
      <Segmented
        label="Min fit"
        options={FIT_OPTIONS}
        value={filters.minFit}
        onChange={(v) => setFilters((f) => ({ ...f, minFit: v }))}
      />
      <Segmented
        label="Sponsorship"
        options={SPONSOR_OPTIONS}
        value={filters.sponsorship}
        onChange={(v) => setFilters((f) => ({ ...f, sponsorship: v }))}
      />
      <label className="flex items-center gap-2 text-xs text-slate-300 ml-auto select-none">
        <span className="uppercase tracking-wider text-[10px] text-slate-500">Remote only</span>
        <button
          type="button"
          role="switch"
          aria-checked={filters.remoteOnly}
          onClick={() => setFilters((f) => ({ ...f, remoteOnly: !f.remoteOnly }))}
          className={`relative w-10 h-5 rounded-full transition-colors ${
            filters.remoteOnly ? "bg-emerald-500" : "bg-slate-700"
          }`}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
              filters.remoteOnly ? "translate-x-5" : ""
            }`}
          />
        </button>
      </label>
    </div>
  );
}
