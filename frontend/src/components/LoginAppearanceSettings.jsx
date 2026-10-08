import { useEffect, useRef, useState } from "react";
import api, { errMsg } from "@/lib/api";
import LoginBackground from "@/components/LoginBackground";
import { Button } from "@/components/ui/button";
import { Image, Upload, Loader2, RotateCcw } from "lucide-react";
import { toast } from "sonner";

const PRESETS = [
  { id: "aurora", name: "Aurora Brand", description: "Biru, cyan, dan aksen emas" },
  { id: "blueprint", name: "Blue Ocean", description: "Biru cerah dengan kedalaman" },
  { id: "sunrise", name: "Golden Light", description: "Terang dan hangat" },
];

export default function LoginAppearanceSettings({ company, onSaved }) {
  const saved = company?.login_background || {};
  const [preset, setPreset] = useState(saved.preset || "aurora");
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const input = useRef(null);
  useEffect(() => { setPreset(company?.login_background?.preset || "aurora"); }, [company]);
  useEffect(() => {
    if (!file) { setPreviewUrl(""); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const chooseFile = (event) => {
    const selected = event.target.files?.[0];
    event.target.value = "";
    if (!selected) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(selected.type)) { toast.error("Gunakan JPG, PNG, atau WEBP"); return; }
    if (selected.size > 3 * 1024 * 1024) { toast.error("Ukuran background maksimal 3MB"); return; }
    setFile(selected);
    setPreset("image");
  };

  const persist = async (reset = false) => {
    setSaving(true);
    try {
      let data;
      if (file && preset === "image" && !reset) {
        const body = new FormData(); body.append("file", file);
        ({ data } = await api.post("/company/login-background", body));
      } else {
        ({ data } = await api.put("/company/login-background", { preset: reset ? "aurora" : preset, reset_image: reset }));
      }
      onSaved(data);
      setFile(null);
      toast.success(reset ? "Background login dikembalikan ke bawaan" : "Background login diperbarui");
    } catch (error) { toast.error(errMsg(error)); }
    finally { setSaving(false); }
  };

  return (
    <section className="brand-panel p-5" aria-labelledby="login-appearance-title">
      <div className="flex items-center gap-2 mb-2"><Image className="w-5 h-5 text-blue-600" /><h2 id="login-appearance-title" className="font-heading font-semibold text-slate-800">Tampilan Halaman Login</h2></div>
      <p className="text-sm text-slate-500 mb-5">Pilih latar bawaan atau gunakan gambar perusahaan. Kartu login tetap di tengah.</p>
      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <div className="space-y-2" role="group" aria-label="Pilihan background login">
            {PRESETS.map((item) => <button key={item.id} type="button" disabled={saving || !company} aria-pressed={preset === item.id} onClick={() => setPreset(item.id)} data-testid={`login-bg-${item.id}`} className={`w-full text-left break-words rounded-xl border p-3 transition-colors ${preset === item.id ? "border-blue-600 bg-blue-50" : "border-blue-100 bg-white hover:bg-blue-50"}`}><span className="block text-sm font-semibold text-slate-800">{item.name}</span><span className="block text-xs text-slate-500 mt-1">{item.description}</span></button>)}
            {(saved.image || file) && <button type="button" disabled={saving || !company} aria-pressed={preset === "image"} onClick={() => setPreset("image")} className={`w-full text-left break-words rounded-xl border p-3 text-sm ${preset === "image" ? "border-blue-600 bg-blue-50" : "border-blue-100"}`}>Gambar sendiri{file ? ` · ${file.name}` : ""}</button>}
          </div>
          <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseFile} className="hidden" data-testid="login-background-file" />
          <Button type="button" variant="outline" className="mt-3 w-full rounded-xl" disabled={saving || !company} onClick={() => input.current?.click()} data-testid="login-background-upload"><Upload className="w-4 h-4" />Pilih gambar background</Button>
          <p className="text-xs text-slate-500 mt-2">JPG, PNG, WEBP · maks 3MB / 20MP. Disarankan gambar lanskap minimal 1600 × 900 px.</p>
        </div>
        <div>
          <div className="login-background-preview" data-testid="login-background-preview">
            <LoginBackground preset={preset} imageUrl={previewUrl || saved.image || ""} />
            <div className="login-preview-card relative text-center"><p className="text-sm font-heading font-semibold text-slate-900">{company?.app_name || "FieldCollector"}</p><p className="text-xs text-slate-500 mt-1">Selamat datang kembali</p><div className="h-7 border border-blue-100 rounded-lg mt-4" /><div className="h-7 border border-blue-100 rounded-lg mt-2" /><div className="brand-action rounded-lg py-2 text-xs font-semibold mt-3">Masuk ke aplikasi</div></div>
          </div>
          <p className="text-xs text-slate-500 mt-2">Pratinjau tampilan login</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-3 justify-between mt-5 pt-4 border-t border-blue-50">
        <Button type="button" variant="outline" className="rounded-xl" disabled={saving || !company} onClick={() => persist(true)} data-testid="login-background-reset"><RotateCcw className="w-4 h-4" />Kembalikan bawaan</Button>
        <Button type="button" className="rounded-xl" disabled={saving || !company} onClick={() => persist()} data-testid="login-background-save">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan background"}</Button>
      </div>
    </section>
  );
}
