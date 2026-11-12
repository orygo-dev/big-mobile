// PKS UI regression fixtures run locally, without writing production data.
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import assert from "node:assert/strict";
import { chromium, firefox } from "../node_modules/@playwright/test/index.mjs";
const root = path.resolve(process.env.PKS_BUILD_ROOT || "frontend/build");
fs.mkdirSync(".local", { recursive: true });
function fixturePDF(pageCount = 2) {
  const font = 3 + pageCount * 2,
    objects = [
      "<< /Type /Catalog /Pages 2 0 R >>",
      `<< /Type /Pages /Kids [${Array.from({ length: pageCount }, (_, i) => `${3 + i * 2} 0 R`).join(" ")}] /Count ${pageCount} >>`,
    ];
  for (let i = 0; i < pageCount; i++) {
    const landscape = pageCount > 2 && i % 2 === 1,
      w = landscape ? 842 : 595,
      h = landscape ? 595 : 842;
    const stream = `BT /F1 18 Tf 40 ${h - 50} Td (PREVIEW PKS - Halaman ${i + 1}) Tj ET`;
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /Font << /F1 ${font} 0 R >> >> /Contents ${4 + i * 2} 0 R >>`,
      `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    );
  }
  objects.push("<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>");
  let data = "%PDF-1.4\n",
    offsets = [0];
  objects.forEach((o, i) => {
    offsets.push(Buffer.byteLength(data));
    data += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = Buffer.byteLength(data);
  data +=
    `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n` +
    offsets
      .slice(1)
      .map((n) => `${String(n).padStart(10, "0")} 00000 n \n`)
      .join("") +
    `trailer\n<< /Root 1 0 R /Size ${objects.length + 1} >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(data);
}
const pdf = fixturePDF();
const server = http.createServer((req, res) => {
  let file = path.resolve(
    root,
    "." + new URL(req.url, "http://localhost").pathname,
  );
  if (
    !file.startsWith(root + path.sep) ||
    !fs.existsSync(file) ||
    !fs.statSync(file).isFile()
  )
    file = path.join(root, "index.html");
  res.setHeader(
    "Content-Type",
    {
      ".js": "text/javascript",
      ".css": "text/css",
      ".html": "text/html",
      ".wasm": "application/wasm",
    }[path.extname(file)] || "application/octet-stream",
  );
  fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = "http://localhost:" + server.address().port;
try {
  for (const engine of (process.env.PKS_TEST_BROWSERS || "chromium").split(
    ",",
  )) {
    const browser =
      engine === "firefox"
        ? await firefox.launch({ headless: true })
        : await chromium.launch({
            ...(engine === "chrome" ? { channel: "chrome" } : {}),
            headless: true,
          });
    try {
      for (const role of ["admin", "owner"]) {
        const context = await browser.newContext({
            viewport: { width: 1440, height: 1000 },
          }),
          page = await context.newPage(),
          errors = [];
        page.on("pageerror", (e) => errors.push(e.message));
        page.on("console", (message) => {
          if (message.type() === "error" || message.type() === "warning")
            console.log(engine, message.type(), message.text());
        });
        let filePdf = pdf;
        let records = [],
          missing = false,
          generated = 0,
          archived = 0,
          legacy = 0;
        let profile = {
          id: "officer",
          name: "Mitra Contoh",
          email: "mitra@example.com",
          petugas_code: "PTG-001",
          nik: "1234567890123456",
          alamat: "Jalan Petugas, Banjarbaru",
          telepon: "081987654321",
          bank_name: "Bank Contoh",
          bank_branch: "Banjarbaru",
          bank_account_number: "00123456789",
          bank_account_name: "Mitra Contoh",
          status: "aktif",
        };
        await page.route("**/api/**", async (route) => {
          const req = route.request(),
            url = new URL(req.url()),
            p = url.pathname;
          assert(
            !p.startsWith("/api/api/"),
            "Private file requests must use the API prefix exactly once",
          );
          let body = {};
          if (p === "/api/auth/me")
            body = { id: role, role, name: role, email: role + "@example.com" };
          else if (["/api/branding", "/api/company"].includes(p))
            body = { app_name: "BIG Mobile", nama: "PT BERKAT INTIM GENERASI" };
          else if (
            ["/api/chat/unread", "/api/approvals/pending-count"].includes(p)
          )
            body = { count: 0 };
          else if (p === "/api/pks/officers")
            body = {
              items: [
                {
                  ...profile,
                  pks_status:
                    records.find((r) => r.source === "GENERATED")?.status ||
                    "BELUM_MEMILIKI",
                },
              ],
              next_page: null,
            };
          else if (p === "/api/petugas/officer")
            body = {
              ...profile,
              bank_account_number: missing ? "" : profile.bank_account_number,
            };
          else if (p === "/api/petugas") body = [profile];
          else if (p === "/api/pks/period") {
            const years = Number(url.searchParams.get("duration"));
            body = {
              start_date: "2026-11-12",
              end_date: `${2026 + years}-11-11`,
              timezone: "Asia/Jakarta",
            };
          } else if (p === "/api/pks/preview") {
            const data = req.postDataJSON();
            assert.deepEqual(Object.keys(data).sort(), [
              "duration",
              "officer_id",
              "unit",
            ]);
            assert.equal(data.duration, 3);
            if (missing)
              return route.fulfill({
                status: 400,
                contentType: "application/json",
                body: JSON.stringify({
                  detail: "Lengkapi nomor rekening di menu Petugas.",
                }),
              });
            return route.fulfill({ contentType: "application/pdf", body: pdf });
          } else if (p === "/api/pks/generate") {
            const data = req.postDataJSON();
            assert.equal(data.duration, 3);
            assert.equal(data.officer_id, "officer");
            assert(data.submission_id);
            assert(!("name" in data));
            generated++;
            body = {
              id: "generated",
              source: "GENERATED",
              officer_name: profile.name,
              officer_code: profile.petugas_code,
              start_date: "2026-11-12",
              end_date: "2029-11-11",
              duration: 3,
              duration_unit: "TAHUN",
              document_number: "007/BIG-PKSM/XI/2026",
              document_status: "DRAFT",
              status: "DRAFT",
              url: "/api/files/generated.pdf",
            };
            records.push(body);
          } else if (p === "/api/pks/generated/signed") {
            assert(
              req
                .postDataBuffer()
                .includes(Buffer.from('filename="signed.pdf"')),
            );
            archived++;
            records = records.map((r) =>
              r.id === "generated"
                ? {
                    ...r,
                    status: "AKTIF",
                    document_status: "SIGNED_ARCHIVED",
                    signed_url: "/api/files/signed.pdf",
                  }
                : r,
            );
            body = records.find((r) => r.id === "generated");
          } else if (p === "/api/pks/generated/delete") {
            assert(req.postDataJSON().reason.length >= 3);
            records = records.filter((r) => r.id !== "generated");
            body = { ok: true };
          } else if (p === "/api/pks" && req.method() === "POST") {
            assert(
              req
                .postDataBuffer()
                .includes(Buffer.from('filename="legacy.pdf"')),
            );
            legacy++;
            body = {
              id: "legacy",
              officer_name: profile.name,
              officer_code: profile.petugas_code,
              start_date: "2026-11-12",
              end_date: "2027-11-11",
              duration: 1,
              duration_unit: "TAHUN",
              status: "AKTIF",
              url: "/api/files/legacy.pdf",
            };
            records.push(body);
          } else if (p === "/api/pks")
            body = {
              items: records.filter(
                (r) =>
                  !url.searchParams.get("state") ||
                  r.status === url.searchParams.get("state"),
              ),
              next_page: null,
            };
          else if (p.startsWith("/api/files/"))
            return route.fulfill({
              contentType: "application/pdf",
              body: filePdf,
            });
          await route.fulfill({
            contentType: "application/json",
            body: JSON.stringify(body),
          });
        });
        await page.goto(origin + "/admin/pks");
        await page.getByTestId("pks-create").click();
        assert(await page.getByTestId("pks-mode-generate").isChecked());
        assert.equal(
          await page
            .getByRole("listbox", { name: "Daftar petugas PKS" })
            .count(),
          0,
        );
        await page.getByTestId("pks-officer-search").click();
        await page.getByTestId("pks-officer-officer").click();
        assert.equal(
          await page
            .getByRole("listbox", { name: "Daftar petugas PKS" })
            .count(),
          0,
        );
        await page.getByTestId("pks-identity-bank_account_number").waitFor();
        assert.equal(
          await page
            .getByTestId("pks-identity-bank_account_number")
            .inputValue(),
          "00123456789",
        );
        assert(
          (await page
            .getByTestId("pks-identity-nik")
            .getAttribute("readonly")) !== null,
        );
        await page.getByTestId("pks-duration").fill("3");
        await page.waitForFunction(() =>
          document
            .querySelector('[data-testid="pks-end"]')
            .value.includes("2029"),
        );
        assert(
          (await page.getByTestId("pks-start").getAttribute("readonly")) !==
            null,
        );
        missing = true;
        await page
          .getByRole("button", { name: "Muat ulang data petugas" })
          .click();
        await page.waitForFunction(
          () =>
            document.querySelector(
              '[data-testid="pks-identity-bank_account_number"]',
            )?.value === "",
        );
        await page.getByTestId("pks-preview").click();
        await page
          .getByRole("alert")
          .filter({ hasText: "Lengkapi nomor rekening" })
          .waitFor();
        missing = false;
        await page
          .getByRole("button", { name: "Muat ulang data petugas" })
          .click();
        await page.waitForFunction(
          () =>
            document.querySelector(
              '[data-testid="pks-identity-bank_account_number"]',
            )?.value === "00123456789",
        );
        await page.getByTestId("pks-preview").click();
        await page.getByTestId("pdf-page-1").locator("canvas").waitFor();
        await page.waitForFunction(
          () =>
            document.querySelector('[data-testid="pks-pdf-preview"] canvas')
              ?.width > 0,
        );
        await page
          .getByTestId("pdf-page-count")
          .filter({ hasText: "2 halaman" })
          .waitFor();
        const continuous = page.getByTestId("pdf-scroll-container");
        await continuous.scrollIntoViewIfNeeded();
        await continuous.hover();
        await page.mouse.wheel(0, 1200);
        await page.waitForFunction(
          () =>
            document.querySelector('[data-testid="pdf-scroll-container"]')
              ?.scrollTop > 0,
        );
        await page
          .getByTestId("pdf-page-2")
          .locator("canvas")
          .waitFor({ state: "visible" });
        assert.equal(
          await page
            .getByRole("dialog")
            .getByRole("button", { name: "Berikutnya", exact: true })
            .count(),
          0,
        );
        await page.screenshot({
          path: `.local/pks-${engine}-${role}-draft.png`,
          fullPage: true,
        });
        await page.getByTestId("pks-save").click();
        await page.getByRole("dialog").waitFor({ state: "detached" });
        await page.getByTestId("pks-row").waitFor();
        await page
          .getByTestId("pks-row")
          .getByText("Draft · Belum Ditandatangani", { exact: true })
          .waitFor();
        assert.equal(generated, 1);
        profile = { ...profile, name: "Nama Diubah" };
        assert(
          (await page.getByTestId("pks-row").innerText()).includes(
            "Mitra Contoh",
          ),
        );
        await page.getByTestId("pks-signed-generated").click();
        await page.getByTestId("pks-signed-file").setInputFiles({
          name: "signed.pdf",
          mimeType: "application/pdf",
          buffer: pdf,
        });
        await page.getByTestId("pks-signed-save").click();
        await page.getByRole("dialog").waitFor({ state: "detached" });
        await page.getByText("Arsip ditandatangani", { exact: true }).waitFor();
        assert.equal(archived, 1);
        await page
          .getByRole("button", { name: "Draft asli", exact: true })
          .waitFor();
        await page
          .getByRole("button", { name: "Lihat PKS", exact: true })
          .click();
        await page.getByTestId("pks-pdf-preview").waitFor();
        await page
          .getByTestId("pdf-page-count")
          .filter({ hasText: "2 halaman" })
          .waitFor();
        await page.getByTestId("pdf-page-1").locator("canvas").waitFor();
        assert(
          (
            await page
              .getByRole("link", { name: "Unduh PDF", exact: true })
              .getAttribute("href")
          ).startsWith("blob:"),
        );
        // Resize an already-open preview: fixed-width canvases must not widen the dialog.
        await page.setViewportSize({ width: 390, height: 844 });
        await page.waitForFunction(() => {
          const dialog = document.querySelector('[role="dialog"]');
          return dialog && dialog.scrollWidth <= dialog.clientWidth;
        });
        await page.getByTestId("pdf-scroll-container").focus();
        await page.keyboard.press("End");
        await page
          .getByTestId("pdf-page-2")
          .locator("canvas")
          .waitFor({ state: "visible" });
        await page.setViewportSize({ width: 1440, height: 1000 });
        await page.waitForFunction(() => {
          const dialog = document.querySelector('[role="dialog"]');
          return dialog && dialog.scrollWidth <= dialog.clientWidth;
        });
        await page.keyboard.press("Escape");
        await page.getByRole("dialog").waitFor({ state: "detached" });
        await page.getByTestId("pks-create").click();
        await page.getByTestId("pks-mode-upload").check();
        await page.getByTestId("pks-officer-search").click();
        await page.getByTestId("pks-officer-officer").click();
        await page.getByTestId("pks-file").setInputFiles({
          name: "legacy.pdf",
          mimeType: "application/pdf",
          buffer: pdf,
        });
        await page.getByTestId("pks-save").click();
        await page.getByRole("dialog").waitFor({ state: "detached" });
        assert.equal(legacy, 1);
        await page.waitForFunction(
          () =>
            document.querySelectorAll('[data-testid="pks-row"]').length === 2,
        );
        assert.equal(await page.getByTestId("pks-row").count(), 2);
        await page.getByTestId("pks-delete-generated").click();
        await page.getByTestId("delete-reason").fill("Koreksi PKS pengujian");
        await page.getByTestId("confirm-delete-button").click();
        await page.getByRole("dialog").waitFor({ state: "detached" });
        await page.waitForFunction(
          () =>
            document.querySelectorAll('[data-testid="pks-row"]').length === 1,
        );
        await page.setViewportSize({ width: 390, height: 844 });
        filePdf = fixturePDF(40);
        await page
          .getByRole("button", { name: "Lihat PKS", exact: true })
          .click();
        await page
          .getByTestId("pdf-page-count")
          .filter({ hasText: "40 halaman" })
          .waitFor();
        await page.getByTestId("pdf-page-1").locator("canvas").waitFor();
        assert.equal(await page.locator("[data-page-number]").count(), 40);
        assert(
          (await page
            .locator('[data-testid="pks-pdf-preview"] canvas')
            .count()) < 10,
        );
        const scroll = page.getByTestId("pdf-scroll-container");
        await scroll.focus();
        await page.keyboard.press("End");
        await page
          .getByTestId("pdf-page-40")
          .locator("canvas")
          .waitFor({ state: "visible" });
        await page
          .getByTestId("pdf-page-1")
          .locator("canvas")
          .waitFor({ state: "detached" });
        assert(
          (await page
            .locator('[data-testid="pks-pdf-preview"] canvas')
            .count()) < 10,
        );
        await scroll.focus();
        await page.keyboard.press("Home");
        await page
          .getByTestId("pdf-page-1")
          .locator("canvas")
          .waitFor({ state: "visible" });
        await page.keyboard.press("Escape");
        await page.getByRole("dialog").waitFor({ state: "detached" });

        await page.getByTestId("pks-create").click();
        await page.getByTestId("pks-officer-search").click();
        await page.getByTestId("pks-officer-officer").click();
        await page.getByTestId("pks-identity-name").waitFor();
        await page.screenshot({
          path: `.local/pks-${engine}-${role}-mobile.png`,
          fullPage: true,
        });
        assert.equal(
          await page
            .getByRole("dialog")
            .evaluate((e) => e.scrollWidth > e.clientWidth),
          false,
        );
        assert.equal(errors.length, 0, errors.join("\n"));
        console.log(
          `PASS PKS ${engine}/${role}: picker, authoritative identity, read-only fields, missing-data validation, PDF.js preview/pages/download, draft generation, signed archive, old upload, scoped delete, mobile, continuous wheel/keyboard scrolling and bounded canvases for 40 mixed-size pages`,
        );
        await context.close();
      }
    } finally {
      await browser.close();
    }
  }
} finally {
  await new Promise((r) => server.close(r));
}
