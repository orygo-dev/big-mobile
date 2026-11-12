import { useEffect, useRef, useState } from "react";
import {
  getDocument,
  GlobalWorkerOptions,
  version as pdfVersion,
} from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
GlobalWorkerOptions.workerSrc = workerUrl;

function PageCanvas({ pdf, number, width, height }) {
  const canvas = useRef(null);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true,
      task;
    const element = canvas.current;
    setLoading(true);
    setError("");
    pdf
      .getPage(number)
      .then((page) => {
        if (!active) return;
        const original = page.getViewport({ scale: 1 }),
          ratio = Math.min(window.devicePixelRatio || 1, 2),
          viewport = page.getViewport({
            scale: (width / original.width) * ratio,
          });
        if (
          !Number.isFinite(viewport.width) ||
          !Number.isFinite(viewport.height) ||
          viewport.width <= 0 ||
          viewport.height <= 0 ||
          viewport.height > 16000 ||
          viewport.width * viewport.height > 12000000
        )
          throw new Error("Page too large");
        element.width = Math.ceil(viewport.width);
        element.height = Math.ceil(viewport.height);
        task = page.render({
          canvasContext: element.getContext("2d"),
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
            `Halaman ${number} tidak dapat ditampilkan. Gunakan Buka / Cetak PDF atau Unduh PDF.`,
          );
          setLoading(false);
        }
      });
    return () => {
      active = false;
      task?.cancel();
      element.width = 0;
      element.height = 0;
    };
  }, [pdf, number, width]);
  return (
    <>
      <canvas
        ref={canvas}
        style={{ width, height }}
        className="block bg-white"
        aria-label={`Preview PDF halaman ${number}`}
      />
      {loading && (
        <div
          role="status"
          className="absolute inset-0 flex items-start justify-center pt-5"
        >
          <span className="rounded-lg bg-white p-2 text-xs shadow">
            Memuat halaman {number}…
          </span>
        </div>
      )}
      {error && (
        <p
          role="alert"
          className="absolute inset-x-3 top-4 rounded-lg bg-white p-3 text-sm text-red-700"
        >
          {error}
        </p>
      )}
    </>
  );
}

export default function PdfReadOnlyPreview({ blob, filename = "PKS.pdf" }) {
  const host = useRef(null),
    slots = useRef([]);
  const [document, setDocument] = useState(null),
    [width, setWidth] = useState(600),
    [error, setError] = useState(""),
    [url, setUrl] = useState(""),
    [nearby, setNearby] = useState(() => new Set());
  useEffect(() => {
    const href = URL.createObjectURL(blob);
    setUrl(href);
    return () => URL.revokeObjectURL(href);
  }, [blob]);
  useEffect(() => {
    let active = true,
      task;
    setDocument(null);
    setError("");
    setNearby(new Set());
    if (host.current) host.current.scrollTop = 0;
    (async () => {
      const bytes = await blob.arrayBuffer();
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
      const pdf = await task.promise;
      if (!active) return;
      if (
        !Number.isInteger(pdf.numPages) ||
        pdf.numPages < 1 ||
        pdf.numPages > 200
      )
        throw new Error("Page count out of bounds");
      // Resolve page dimensions before laying them out, so landscape/mixed pages do not jump on scroll.
      const pages = Array(pdf.numPages);
      let next = 0;
      await Promise.all(
        Array.from({ length: Math.min(4, pdf.numPages) }, async () => {
          while (active && next < pdf.numPages) {
            const index = next++;
            try {
              const page = await pdf.getPage(index + 1),
                viewport = page.getViewport({ scale: 1 }),
                aspect = viewport.height / viewport.width;
              if (!Number.isFinite(aspect) || aspect <= 0 || aspect > 100)
                throw new Error("Invalid page");
              pages[index] = { number: index + 1, aspect };
            } catch {
              pages[index] = { number: index + 1, error: true, aspect: 1 };
            }
          }
        }),
      );
      if (active) setDocument({ pdf, pages });
    })().catch(() => {
      if (active)
        setError(
          "Preview PDF tidak dapat dimuat. Gunakan Buka / Cetak PDF atau Unduh PDF.",
        );
    });
    return () => {
      active = false;
      task?.destroy().catch(() => {});
    };
  }, [blob]);
  useEffect(() => {
    const resize = () =>
      setWidth(
        Math.max(100, Math.min(900, Math.floor(host.current.clientWidth - 16))),
      );
    const observer = new ResizeObserver(resize);
    if (host.current) {
      resize();
      observer.observe(host.current);
    }
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!document) return;
    // Keep only nearby canvases in memory; page slots retain their dimensions for continuous scrolling.
    const observer = new IntersectionObserver(
      (entries) =>
        setNearby((previous) => {
          const next = new Set(previous);
          let changed = false;
          for (const entry of entries) {
            const number = Number(entry.target.dataset.pageNumber);
            if (entry.isIntersecting && !next.has(number)) {
              next.add(number);
              changed = true;
            } else if (!entry.isIntersecting && next.has(number)) {
              next.delete(number);
              changed = true;
            }
          }
          return changed ? next : previous;
        }),
      { root: host.current, rootMargin: "500px 0px" },
    );
    slots.current.forEach((slot) => {
      if (slot) observer.observe(slot);
    });
    return () => observer.disconnect();
  }, [document]);
  return (
    <div className="space-y-3 min-w-0" data-testid="pks-pdf-preview">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="text-xs text-slate-600" data-testid="pdf-page-count">
          {document
            ? `${document.pages.length} halaman · Gulir untuk membaca seluruh dokumen`
            : "Memuat dokumen…"}
        </span>
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
        tabIndex={0}
        role="region"
        aria-label="Dokumen PDF. Gulir ke bawah untuk membaca halaman berikutnya."
        data-testid="pdf-scroll-container"
        className="relative rounded-xl border bg-slate-100 p-2 overflow-auto h-[65vh] min-h-48 min-w-0 w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        style={{ scrollbarGutter: "stable" }}
      >
        {!document && !error && (
          <p role="status" className="p-4 text-center text-sm text-slate-500">
            Memuat halaman PDF…
          </p>
        )}
        {document?.pages.map((page, index) => {
          const height = Math.ceil(width * page.aspect),
            ratio = Math.min(window.devicePixelRatio || 1, 2),
            tooLarge =
              page.error ||
              height * ratio > 16000 ||
              width * height * ratio * ratio > 12000000;
          return (
            <figure
              key={page.number}
              ref={(element) => {
                slots.current[index] = element;
              }}
              data-page-number={page.number}
              data-testid={`pdf-page-${page.number}`}
              className="mx-auto mb-4 last:mb-0 max-w-full"
              style={{ width }}
            >
              <div
                className="relative overflow-hidden bg-white shadow-sm"
                style={{ height: tooLarge ? 160 : height }}
              >
                {tooLarge ? (
                  <p role="alert" className="p-4 text-sm text-red-700">
                    Halaman {page.number} terlalu besar untuk preview. Gunakan
                    Buka / Cetak PDF atau Unduh PDF.
                  </p>
                ) : nearby.has(page.number) ? (
                  <PageCanvas
                    key={`${page.number}-${width}`}
                    pdf={document.pdf}
                    number={page.number}
                    width={width}
                    height={height}
                  />
                ) : (
                  <p className="p-4 text-center text-xs text-slate-400">
                    Halaman {page.number}
                  </p>
                )}
              </div>
              <figcaption className="pt-2 text-center text-xs text-slate-500">
                Halaman {page.number} dari {document.pages.length}
              </figcaption>
            </figure>
          );
        })}
      </div>
    </div>
  );
}
