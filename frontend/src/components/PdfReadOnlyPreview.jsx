import { useEffect, useRef, useState } from "react";
import {
  getDocument,
  GlobalWorkerOptions,
  version as pdfVersion,
} from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { Button } from "@/components/ui/button";
GlobalWorkerOptions.workerSrc = workerUrl;

export default function PdfReadOnlyPreview({ blob, filename = "PKS.pdf" }) {
  const host = useRef(null),
    canvas = useRef(null);
  const [pdf, setPdf] = useState(null),
    [page, setPage] = useState(1),
    [width, setWidth] = useState(600),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [url, setUrl] = useState("");
  useEffect(() => {
    const href = URL.createObjectURL(blob);
    setUrl(href);
    return () => URL.revokeObjectURL(href);
  }, [blob]);
  useEffect(() => {
    let active = true,
      task;
    setPdf(null);
    setPage(1);
    setError("");
    setLoading(true);
    blob
      .arrayBuffer()
      .then((bytes) => {
        if (!active) return;
        task = getDocument({
          data: new Uint8Array(bytes),
          cMapUrl: `/pdfjs/${pdfVersion}/cmaps/`,
          cMapPacked: true,
          standardFontDataUrl: `/pdfjs/${pdfVersion}/standard_fonts/`,
          wasmUrl: `/pdfjs/${pdfVersion}/wasm/`,
          isEvalSupported: false,
          useWasm: false,
          disableFontFace: true,
          stopAtErrors: true,
        });
        return task.promise;
      })
      .then((doc) => {
        if (active && doc) setPdf(doc);
      })
      .catch(() => {
        if (active) {
          setError(
            "Preview PDF tidak dapat dimuat. Gunakan Buka / Cetak PDF atau Unduh PDF.",
          );
          setLoading(false);
        }
      });
    return () => {
      active = false;
      task?.destroy();
    };
  }, [blob]);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(150, Math.min(900, entry.contentRect.width - 16))),
    );
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!pdf) return;
    let active = true,
      task;
    setLoading(true);
    setError("");
    pdf
      .getPage(page)
      .then((p) => {
        if (!active || !canvas.current) return;
        const original = p.getViewport({ scale: 1 }),
          scale = width / original.width,
          ratio = Math.min(window.devicePixelRatio || 1, 2),
          viewport = p.getViewport({ scale: scale * ratio });
        if (
          !Number.isFinite(viewport.width) ||
          !Number.isFinite(viewport.height) ||
          viewport.width <= 0 ||
          viewport.height <= 0 ||
          viewport.height > 16000 ||
          viewport.width * viewport.height > 12000000
        ) {
          throw new Error("Ukuran halaman PDF terlalu besar untuk preview.");
        }
        canvas.current.width = viewport.width;
        canvas.current.height = viewport.height;
        canvas.current.style.width = width + "px";
        canvas.current.style.height = viewport.height / ratio + "px";
        task = p.render({
          canvasContext: canvas.current.getContext("2d"),
          viewport,
        });
        return task.promise;
      })
      .then(() => {
        if (active) setLoading(false);
      })
      .catch((e) => {
        if (active && e?.name !== "RenderingCancelledException") {
          setError(
            "Halaman PDF tidak dapat ditampilkan. Silakan buka atau unduh PDF.",
          );
          setLoading(false);
        }
      });
    return () => {
      active = false;
      task?.cancel();
    };
  }, [pdf, page, width]);
  return (
    <div className="space-y-3" data-testid="pks-pdf-preview">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!pdf || page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          Sebelumnya
        </Button>
        <span className="text-xs">
          Halaman {page} / {pdf?.numPages || "…"}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!pdf || page >= pdf.numPages}
          onClick={() => setPage((p) => p + 1)}
        >
          Berikutnya
        </Button>
        <a
          className="text-xs font-semibold text-blue-700 underline"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Buka / Cetak PDF
        </a>
        <a
          className="text-xs font-semibold text-blue-700 underline"
          href={url}
          download={filename}
        >
          Unduh PDF
        </a>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <div
        ref={host}
        className="relative rounded-xl border bg-slate-100 p-2 overflow-auto max-h-[65vh] min-h-48"
      >
        <canvas
          ref={canvas}
          className="mx-auto bg-white shadow-sm"
          aria-label={`Preview PDF halaman ${page}`}
        />
        {loading && (
          <div
            role="status"
            className="absolute top-4 left-4 bg-white rounded-lg p-2 text-xs shadow"
          >
            Memuat halaman PDF…
          </div>
        )}
      </div>
    </div>
  );
}
