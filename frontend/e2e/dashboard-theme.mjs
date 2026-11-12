// Read-only UI regression checks with deterministic API fixtures; no production data is changed.
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import assert from "node:assert/strict";

import { chromium, firefox } from "../node_modules/@playwright/test/index.mjs";

const root = path.resolve(process.env.DASHBOARD_BUILD_ROOT || "frontend/build");
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
      ".png": "image/png",
      ".webp": "image/webp",
    }[path.extname(file)] || "application/octet-stream",
  );
  fs.createReadStream(file).pipe(res);
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = "http://localhost:" + server.address().port;

const logo =
  "data:image/svg+xml," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 55"><text x="4" y="37" font-size="33" fill="#008acb" font-weight="bold">BIG</text><ellipse cx="38" cy="26" rx="35" ry="16" transform="rotate(35 38 26)" fill="none" stroke="red" stroke-width="4"/></svg>',
  );

fs.mkdirSync(".local", { recursive: true });
let tests = 0;

try {
  for (const engine of (
    process.env.DASHBOARD_TEST_BROWSERS || "chromium"
  ).split(",")) {
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
          viewport: { width: 1672, height: 865 },
          timezoneId: "Asia/Shanghai",
        });
        const page = await context.newPage();
        let unread = 3,
          pending = 2,
          fail = false;
        const requests = [],
          errors = [];
        page.on("pageerror", (e) => errors.push(e.message));

        await page.route("**/api/**", async (route) => {
          const url = new URL(route.request().url()),
            p = url.pathname;
          requests.push(p);
          let body = {};

          if (p === "/api/auth/me")
            body = {
              id: role,
              role,
              name: role === "owner" ? "Owner" : "Administrator",
              email: role + "@rebornpartner.xyz",
            };
          else if (["/api/company", "/api/branding"].includes(p))
            body = {
              app_name: "BIG Mobile",
              nama: "PT. BERKAT INTIM GENERASI",
              logo,
            };
          else if (p === "/api/chat/unread") body = { count: unread };
          else if (p === "/api/approvals/pending-count") {
            assert.equal(role, "owner");
            body = { count: pending };
          } else if (p === "/api/dashboard/stats")
            body = {
              surat_kuasa_aktif: 45,
              total_akun: 43,
              tugas_aktif: 18,
              unit_ditemukan: 0,
              unit_tidak_ditemukan: 0,
              belum_dikerjakan: 18,
              laporan_hari_ini: 0,
            };
          else if (p === "/api/dashboard/finance") {
            if (fail)
              return route.fulfill({
                status: 503,
                contentType: "application/json",
                body: JSON.stringify({
                  detail: "Layanan sementara tidak tersedia",
                }),
              });
            body = {
              month: "2026-11",
              income: "0.00",
              expense: "141240000.00",
              profit: "-141240000.00",
            };
          } else if (p === "/api/dashboard/reports-7days")
            body = [3, 0, 0, 2, 1, 0, 0].map((count, i) => ({
              date: `2026-11-${i + 6}`,
              label: `${String(i + 6).padStart(2, "0")}/11`,
              count,
            }));
          else if (p === "/api/dashboard/recent-activity")
            body = [
              "FAJAR RIYADI SH",
              "M YENDI MEIROLLY",
              "Muhammad Andi Saputra",
              "M YENDI MEIROLLY",
              "HADI SUMONO",
            ].map((petugas, i) => ({
              id: `report-${i}`,
              waktu: "2026-11-10T06:53:00Z",
              petugas,
              nomor_surat_tugas: `${624 + i}/BIG-SKS/XI/2026`,
              nama_debitur: [
                "ALBERTUS GUNAWAN",
                "VINDA",
                "MUHAMMAD HASBI",
                "BASRAN",
                "MUAMAR QADAFY",
              ][i],
              status: "LAINNYA",
            }));
          else if (p === "/api/laporan-options")
            body = { items: [], next_page: null };
          else if (p === "/api/akun")
            body = { items: [], total: 0, page: 1, limit: 10 };
          else if (p === "/api/petugas")
            body = [
              {
                id: "officer",
                name: "Noval",
                email: "noval@example.com",
                status: "aktif",
                petugas_code: "PT001",
              },
            ];
          else if (
            ["/api/surat-kuasa", "/api/surat-tugas", "/api/clients", "/api/laporan"].includes(p)
          )
            body = [];
          else if (p === "/api/auth/logout")
            return route.fulfill({
              status: 500,
              contentType: "application/json",
              body: '{"detail":"Logout gagal"}',
            });

          await route.fulfill({
            contentType: "application/json",
            body: JSON.stringify(body),
          });
        });

        await page.goto(origin + "/admin");
        await page.waitForFunction(() =>
          document
            .querySelector('[data-testid="dashboard-finance-profit"]')
            ?.textContent.includes("141.240.000"),
        );

        assert.match(
          await page.getByTestId("dashboard-finance-profit").innerText(),
          /-.*141\.240\.000,00/,
        );
        assert.equal(
          await page.getByTestId("dashboard-stats").locator("section").count(),
          7,
        );
        assert.equal(
          await page.getByTestId("owner-admin-users-link").count(),
          role === "owner" ? 1 : 0,
        );

        await page
          .getByLabel("3 pesan belum dibaca", { exact: true })
          .waitFor();
        if (role === "owner")
          await page.getByTestId("approval-pending-count").waitFor();

        await page.waitForFunction(() => document.querySelector(".dashboard-hero-art")?.naturalWidth > 0);
        assert.deepEqual(
          await page.getByTestId(/^report-bar-label-/).allTextContents(),
          ["3", "0", "0", "2", "1", "0", "0"],
        );
        await page.screenshot({
          path: `.local/dashboard-${engine}-${role}-desktop.png`,
          fullPage: true,
        });

        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );

        await page
          .getByRole("button", { name: "Notifikasi", exact: true })
          .click();
        await page
          .getByRole("menuitem", { name: "3 pesan belum dibaca" })
          .waitFor();
        await page.keyboard.press("Escape");

        unread = 0;
        pending = 0;
        await page.evaluate(() => {
          window.dispatchEvent(new Event("big-mobile-chat-read"));
          window.dispatchEvent(new Event("big-mobile-approval-changed"));
        });
        await page
          .getByLabel("3 pesan belum dibaca", { exact: true })
          .waitFor({ state: "detached" });
        assert.equal(
          await page.getByTestId("approval-pending-count").count(),
          0,
        );

        await page.keyboard.press("Control+k");
        await page
          .getByPlaceholder("Cari kontrak, unit, petugas, atau laporan…")
          .fill("Noval");
        await page
          .getByRole("option", { name: "Cari “Noval” di Petugas" })
          .click();
        await page.getByTestId("petugas-search-input").waitFor();
        assert.equal(
          await page.getByTestId("petugas-search-input").inputValue(),
          "Noval",
        );
        await page.getByTestId("petugas-card-officer").waitFor();

        for (const [label, tid] of [
          ["Kontrak & Unit Baru", "akun-search-input"],
          ["Surat Kuasa Baru", "sk-search-input"],
          ["Penugasan Baru", "penugasan-create-button"],
        ]) {
          await page.getByRole("button", { name: "Buat Baru" }).click();
          await page
            .getByRole("menuitem", { name: label, exact: true })
            .click();
          await page.getByRole("dialog").waitFor();
          assert(!page.url().includes("create=1"));
          await page
            .getByRole("dialog")
            .getByRole("button", { name: "Batal", exact: true })
            .click();
          await page.getByRole("dialog").waitFor({ state: "detached" });
          await page.getByTestId(tid).waitFor();
        }

        await page.getByTestId("penugasan-create-button").click();
        await page.getByRole("dialog").waitFor();
        await page.keyboard.press("Escape");
        await page.getByRole("dialog").waitFor({ state: "detached" });

        await page.goto(origin + "/admin");
        await page.getByTestId("dashboard-finance-profit").waitFor();
        await page
          .getByRole("button", { name: "Lihat Semua", exact: true })
          .click();
        assert(page.url().endsWith("/admin/laporan"));
        await page.getByTestId("laporan-create-button").click();
        const reportDialog = page.getByRole("dialog");
        const received = reportDialog.getByText("Diterima tim", { exact: true }).locator("..");
        await reportDialog.getByTestId("admin-report-amount").fill("500000");
        assert.match(await received.innerText(), /500\.000/);
        await reportDialog.getByTestId("admin-report-tax-rate").fill("2");
        assert.match(await received.innerText(), /490\.000/);
        await reportDialog.getByTestId("admin-report-tax-rate").fill("2.50");
        assert.match(await received.innerText(), /487\.500/);
        await page.keyboard.press("Escape");
        await reportDialog.waitFor({ state: "detached" });

        await page.goto(origin + "/admin");
        await page.getByTestId("activity-view-report-0").waitFor();
        await page.getByTestId("activity-view-report-0").click();
        assert(page.url().includes("/admin/laporan/report-0"));

        await page.goto(origin + "/admin");
        await page.getByTestId("dashboard-finance-profit").waitFor();
        for (const width of [768, 820, 1024, 1280]) {
          await page.setViewportSize({ width, height: 900 });
          await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth);
          assert.equal(
            await page.evaluate(
              () => document.documentElement.scrollWidth > innerWidth,
            ),
            false,
          );
          assert(
            await page.getByRole("button", { name: "Buat Baru" }).isVisible(),
          );
        }
        await page.setViewportSize({ width: 390, height: 844 });
        await page.screenshot({
          path: `.local/dashboard-${engine}-${role}-mobile.png`,
          fullPage: true,
        });
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );

        await page.getByTestId("admin-menu-toggle").click();
        const drawer = page.getByRole("dialog");
        await drawer.getByTestId("admin-sidebar-chat-link").waitFor();
        await page.keyboard.press("Escape");
        await drawer.waitFor({ state: "detached" });

        await page
          .getByRole("button", { name: "Menu akun", exact: true })
          .click();
        await page
          .getByRole("menuitem", { name: "Keluar", exact: true })
          .click();
        await page.getByText("Logout gagal", { exact: true }).waitFor();
        assert(page.url().endsWith("/admin"));

        fail = true;
        await page.reload();
        await page
          .getByText("Layanan sementara tidak tersedia", { exact: true })
          .waitFor();
        fail = false;
        await page.getByRole("button", { name: /Coba lagi/i }).click();
        await page.waitForFunction(() =>
          document
            .querySelector('[data-testid="dashboard-finance-profit"]')
            ?.textContent.includes("141.240.000"),
        );

        assert.equal(errors.length, 0, errors.join("\n"));
        console.log(
          `PASS ${engine}/${role}: financial values, 7 metrics, roles, badges/events, notifications, global search, 3 existing create dialogs, activity links, mobile drawer/overflow, logout error, dashboard recovery`,
        );
        tests++;
        await context.close();
      }
    } finally {
      await browser.close();
    }
  }
} finally {
  await new Promise((resolve) => server.close(resolve));
}
console.log(`PASS ${tests} browser/role combinations`);
