import { Layers } from "lucide-react";
import { useBranding } from "@/context/BrandingContext";

export default function BrandIdentity({ light = false, className = "" }) {
  const { appName, logo } = useBranding();
  return (
    <div className={`flex items-center gap-3 min-w-0 ${className}`}>
      {logo ? (
        <img src={logo} alt={appName} className="h-10 w-auto max-w-[180px] object-contain" />
      ) : (
        <>
          <span className="brand-mark inline-flex rounded-xl p-2 shrink-0"><Layers className="w-5 h-5" aria-hidden="true" /></span>
          <span className={`font-heading font-semibold text-xl tracking-tight break-words min-w-0 ${light ? "text-white" : "text-slate-900"}`}>{appName}</span>
        </>
      )}
    </div>
  );
}
