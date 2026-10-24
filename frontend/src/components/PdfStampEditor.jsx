import { useEffect, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions, version as pdfVersion } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import api, { errMsg, fileUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Save, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

GlobalWorkerOptions.workerSrc = workerUrl;
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

export default function PdfStampEditor({ skId, onSaved, onCancel, onBusyChange }) {
  const [info, setInfo] = useState(null);
  const [sourceId, setSourceId] = useState("");
  const [pdf, setPdf] = useState(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [size, setSize] = useState({ width: 600, height: 850 });
  const [available, setAvailable] = useState(600);
  const [imageFile, setImageFile] = useState(null);
  const [imageUrl, setImageUrl] = useState("");
  const [companyImage, setCompanyImage] = useState(true);
  const [aspect, setAspect] = useState(0);
  const [position, setPosition] = useState({ x: .55, y: .65, width: .3 });
  const [busy, setBusy] = useState(false);
  const [rendered, setRendered] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const canvas = useRef(null), stage = useRef(null), scroller = useRef(null), drag = useRef(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  useEffect(() => {
    let active = true;
    api.get(`/surat-kuasa/${skId}/stamp-info`).then(({ data }) => {
      if (!active) return;
      setInfo(data);
      setSourceId(data.versions.find(v => v.url === data.current_file_url)?.id || "");
      if (!data.signature) setCompanyImage(false);
    }).catch(e => { if (active) setLoadError(errMsg(e)); });
    return () => { active = false; };
  }, [skId]);

  useEffect(() => {
    const observer = new ResizeObserver(entries => setAvailable(Math.max(240, entries[0].contentRect.width - 24)));
    observer.observe(scroller.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let active = true, task;
    const controller = new AbortController();
    setPdf(null); setRendered(false); setLoadError(""); setPage(1);
    const source = info?.versions.find(v => v.id === sourceId);
    if (!source) return;
    if (!source.url?.startsWith('/api/files/')) { setLoadError('URL dokumen tidak valid'); return; }
    api.get(source.url.slice(4), { responseType: 'arraybuffer', signal: controller.signal }).then(async ({ data }) => {
      if (!active) return;
      const assets = `${import.meta.env.BASE_URL}pdfjs/${pdfVersion}/`;
      task = getDocument({ data: new Uint8Array(data), isEvalSupported: false, useWasm: false, disableFontFace: true, stopAtErrors: true,
        cMapUrl: assets + 'cmaps/', cMapPacked: true, standardFontDataUrl: assets + 'standard_fonts/', wasmUrl: assets + 'wasm/' });
      const document = await task.promise;
      if (active) setPdf(document);
    }).catch(e => { if (active) setLoadError(e.response ? errMsg(e) : 'PDF tidak dapat dibuka di editor. Pastikan PDF tidak rusak atau terenkripsi.'); });
    return () => { active = false; controller.abort(); task?.destroy(); };
  }, [info, sourceId]);

  useEffect(() => {
    let active = true, rendering;
    setRendered(false);
    if (!pdf) return;
    pdf.getPage(page).then(async pdfPage => {
      if (!active) return;
      const original = pdfPage.getViewport({ scale: 1 });
      const viewport = pdfPage.getViewport({ scale: Math.min(available, 760) * zoom / original.width });
      setSize({ width: viewport.width, height: viewport.height });
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const element = canvas.current;
      element.width = Math.ceil(viewport.width * ratio); element.height = Math.ceil(viewport.height * ratio);
      rendering = pdfPage.render({ canvasContext: element.getContext('2d'), viewport, transform: [ratio, 0, 0, ratio, 0, 0] });
      await rendering.promise;
      if (active) { setRendered(true); setLoadError(""); }
    }).catch(e => { if (active && e.name !== 'RenderingCancelledException') setLoadError('Halaman PDF gagal ditampilkan. Pilih halaman lain atau buka kembali editor.'); });
    return () => { active = false; rendering?.cancel(); };
  }, [pdf, page, available, zoom]);

  useEffect(() => {
    setAspect(0);
    if (companyImage) { setImageUrl(info?.signature || ""); return; }
    if (!imageFile) { setImageUrl(""); return; }
    const url = URL.createObjectURL(imageFile); setImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [companyImage, imageFile, info]);

  const pageAspect = size.width / size.height;
  const width = Math.min(position.width, aspect ? aspect / pageAspect * .95 : .95);
  const height = aspect ? width * pageAspect / aspect : 0;
  const x = clamp(position.x, 0, 1 - width), y = clamp(position.y, 0, 1 - height);
  const moveTo = (clientX, clientY, offsetX = width / 2, offsetY = height / 2) => {
    const rect = stage.current.getBoundingClientRect();
    setPosition(p => ({ ...p, x: clamp((clientX - rect.left) / rect.width - offsetX, 0, 1 - width),
      y: clamp((clientY - rect.top) / rect.height - offsetY, 0, 1 - height) }));
  };
  const save = async () => {
    if (busy || !rendered || !imageUrl || !aspect) return;
    setBusy(true); onBusyChange?.(true); setError("");
    const body = new FormData();
    body.append('source_document_id', sourceId); body.append('expected_file_url', info.current_file_url);
    body.append('placement', JSON.stringify({ page, x, y, width, height }));
    body.append('use_company_signature', String(companyImage));
    if (!companyImage) body.append('image', imageFile);
    try {
      const { data } = await api.post(`/surat-kuasa/${skId}/stamp`, body, { timeout: 120000 });
      if (mounted.current) { toast.success('Salinan PDF dengan tanda tangan/stempel berhasil disimpan'); onSaved(data.file_url); }
    } catch (e) { if (mounted.current) setError(errMsg(e)); }
    finally { onBusyChange?.(false); if (mounted.current) setBusy(false); }
  };

  return <div className="space-y-3 min-w-0 w-full max-w-full" data-testid="pdf-stamp-editor">
    <p className="text-sm text-slate-600">Pilih halaman, lalu klik halaman atau geser gambar ke posisi yang diinginkan. PDF asli tetap disimpan. Hasil menjadi dokumen terbaru untuk semua unit yang menggunakan Surat Kuasa ini.</p>
    <fieldset disabled={busy} className="grid sm:grid-cols-2 gap-3 min-w-0">
      <div className="min-w-0"><Label htmlFor="stamp-source">Versi dokumen sumber</Label><select id="stamp-source" className="border rounded-lg p-2 w-full max-w-full text-sm" value={sourceId} onChange={e => { setSourceId(e.target.value); setError(''); }}>
        {!sourceId && <option value="">Pilih dokumen</option>}
        {info?.versions.map((v, index) => <option key={v.id} value={v.id}>{v.stamped ? 'Hasil stempel' : 'Dokumen unggahan'} — {v.created_at ? new Date(v.created_at).toLocaleString('id-ID') : v.filename || index + 1}{v.url === info.current_file_url ? ' (terbaru)' : ''}</option>)}
      </select>{sourceId && <a className="text-sm text-blue-600 underline" href={fileUrl(info.versions.find(v => v.id === sourceId)?.url)} target="_blank" rel="noreferrer">Buka / unduh versi sumber</a>}</div>
      <div className="min-w-0"><Label htmlFor="stamp-image-source">Gambar tanda tangan / stempel</Label><select id="stamp-image-source" value={companyImage ? 'company' : 'upload'} onChange={e => setCompanyImage(e.target.value === 'company')} className="border rounded-lg p-2 w-full max-w-full text-sm">
        <option value="company" disabled={!info?.signature}>Tanda tangan/stempel dari Pengaturan</option><option value="upload">Unggah gambar sendiri</option>
      </select></div>
      {!companyImage && <div className="sm:col-span-2"><Input aria-label="Unggah gambar tanda tangan atau stempel" type="file" accept="image/png,image/jpeg,image/webp" onChange={e => {
        const file = e.target.files?.[0]; setError('');
        if (file && (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024)) {
          setError('Gunakan PNG/JPEG/WebP maksimal 2MB'); e.target.value = ''; setImageFile(null); return;
        } setImageFile(file || null);
      }} /><p className="text-xs text-slate-500 mt-1">PNG transparan disarankan. Maksimal 2MB, 12 megapiksel.</p></div>}
      <div className="flex items-center gap-2 text-sm"><Label htmlFor="stamp-page">Halaman</Label><select id="stamp-page" value={page} onChange={e => setPage(Number(e.target.value))} disabled={!pdf || busy} className="border rounded p-1">{Array.from({ length: pdf?.numPages || 1 }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}</select><span>/ {pdf?.numPages || '—'}</span>
        <Label htmlFor="stamp-zoom">Zoom</Label><select id="stamp-zoom" value={zoom} onChange={e => setZoom(Number(e.target.value))} className="border rounded p-1"><option value={1}>100%</option><option value={1.25}>125%</option><option value={1.5}>150%</option></select></div>
      <div><Label htmlFor="stamp-size">Ukuran gambar ({Math.round(width * 100)}% lebar halaman)</Label><input id="stamp-size" type="range" min=".05" max=".8" step=".005" value={position.width} onChange={e => setPosition(p => ({ ...p, width: Number(e.target.value) }))} className="w-full" /></div>
    </fieldset>
    {(loadError || error) && <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg p-3">{loadError || error}</p>}
    <div ref={scroller} className="bg-slate-200 rounded-xl overflow-auto max-h-[52vh] p-3 min-w-0 w-full max-w-full" aria-busy={!rendered}>
      {!rendered && !loadError && <p className="flex gap-2 items-center text-sm p-3"><Loader2 className="h-4 w-4 animate-spin" />Memuat halaman PDF…</p>}
      <div ref={stage} data-testid="stamp-page-canvas" style={{ width: size.width, height: size.height, position: 'relative', display: rendered ? 'block' : 'none', margin: '0 auto' }}
        onPointerDown={e => { if (e.target === canvas.current && !busy && aspect) moveTo(e.clientX, e.clientY); }}>
        <canvas ref={canvas} style={{ width: '100%', height: '100%' }} />
        {imageUrl && <button type="button" aria-label="Geser tanda tangan atau stempel" disabled={busy} data-testid="stamp-draggable" className="absolute border-2 border-dashed border-blue-500 focus:ring-2 ring-orange-400 cursor-move bg-transparent p-0" style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${width * 100}%`, height: height ? `${height * 100}%` : 'auto', touchAction: 'none' }}
          onPointerDown={e => { if (busy || !aspect) return; const rect = stage.current.getBoundingClientRect(); drag.current = { x: (e.clientX - rect.left) / rect.width - x, y: (e.clientY - rect.top) / rect.height - y }; e.currentTarget.setPointerCapture(e.pointerId); }}
          onPointerMove={e => { if (drag.current && !busy) moveTo(e.clientX, e.clientY, drag.current.x, drag.current.y); }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}
          onKeyDown={e => { const deltas = { ArrowLeft: [-.01, 0], ArrowRight: [.01, 0], ArrowUp: [0, -.01], ArrowDown: [0, .01] }; const delta = deltas[e.key]; if (delta) { e.preventDefault(); setPosition(p => ({ ...p, x: clamp(x + delta[0], 0, 1 - width), y: clamp(y + delta[1], 0, 1 - height) })); } }}>
          <img src={imageUrl} alt="Tanda tangan/stempel yang akan ditempatkan" className="w-full h-full object-contain pointer-events-none" draggable={false} onLoad={e => {
            const img = e.currentTarget;
            if (img.naturalWidth * img.naturalHeight > 12_000_000) { setAspect(0); setError('Resolusi gambar maksimal 12 megapiksel'); }
            else setAspect(img.naturalWidth / img.naturalHeight);
          }} onError={() => { setAspect(0); setError('Gambar tidak dapat dibuka. Pilih gambar lain.'); }} />
        </button>}
      </div>
    </div>
    <p className="text-xs text-slate-500">Gunakan tombol panah saat gambar dipilih untuk menggeser secara presisi. Untuk menambahkan stempel berikutnya, buka kembali editor dan pilih versi hasil terakhir. Ini berupa gambar, bukan tanda tangan elektronik tersertifikasi.</p>
    <div className="flex justify-between gap-2"><Button variant="outline" disabled={busy} onClick={onCancel}><ArrowLeft className="h-4 w-4 mr-1" />Kembali</Button><Button disabled={busy || !rendered || !aspect || !sourceId || !!loadError} onClick={save} data-testid="stamp-save">{busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}Simpan Salinan PDF</Button></div>
  </div>;
}
