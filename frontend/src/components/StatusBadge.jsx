export function StatusBadge({ map, value, dataTestid }) {
  const info = map[value] || { label: value || "-", cls: "bg-slate-100 text-slate-700 border-slate-200" };
  return (
    <span
      data-testid={dataTestid}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${info.cls}`}
    >
      {info.label}
    </span>
  );
}
