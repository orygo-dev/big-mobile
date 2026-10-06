export default function EmptyState({ icon: Icon, title, desc, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-14 px-6">
      {Icon && (
        <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
          <Icon className="w-7 h-7 text-slate-400" />
        </div>
      )}
      <h3 className="font-heading font-semibold text-slate-800 text-lg">{title}</h3>
      {desc && <p className="text-sm text-slate-500 mt-1 max-w-sm">{desc}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
