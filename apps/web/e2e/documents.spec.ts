import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";

const ownerEmail = process.env.F03_E2E_OWNER_EMAIL;
const ownerPassword = process.env.F03_E2E_OWNER_PASSWORD;
const appAdminEmail = process.env.F03_E2E_APP_ADMIN_EMAIL;
const appAdminPassword = process.env.F03_E2E_APP_ADMIN_PASSWORD;
const python = process.env.F03_E2E_PYTHON;
const browserPath = process.env.F03_E2E_BROWSER_PATH;
const webUrl = process.env.F03_E2E_WEB_URL ?? "http://localhost:3000";
test.use({ launchOptions: browserPath ? { executablePath: browserPath } : undefined });

async function login(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto(`${webUrl}/login`);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(`${webUrl}/dashboard`);
}

test("owner workflow and App Admin metadata separation remain content-safe", async ({ page, context }) => {
  test.skip(!ownerEmail || !ownerPassword || !appAdminEmail || !appAdminPassword || !python,
    "F-03 native MySQL E2E environment is required");
  const marker = `SYNTHETIC-F03-${Date.now()}`;
  const filename = `sensitive-${Date.now()}.txt`;
  const uploadPath = path.join(process.cwd(), filename);
  fs.writeFileSync(uploadPath, marker, { encoding: "utf8", mode: 0o600 });
  const observed: string[] = [];
  page.on("console", message => observed.push(message.text()));
  try {
    await login(page, ownerEmail!, ownerPassword!);
    await page.goto(`${webUrl}/documents`);
    await page.getByLabel("Title").fill("Browser runbook");
    await page.getByLabel("Description").fill("Browser acceptance");
    await page.getByLabel("File").setInputFiles(uploadPath);
    await page.getByRole("button", { name: "Upload document" }).click();
    await expect(page.getByRole("status")).toHaveText("Document uploaded");
    execFileSync("powershell.exe", ["-NoProfile", "-Command",
      "& $env:F03_E2E_PYTHON manage.py process_documents --once"],
      { cwd: path.resolve(process.cwd(), "../api"), stdio: "pipe" });
    await page.reload();
    await expect(page.getByText("active · ready")).toBeVisible();
    const download = await context.request.get(await page.getByRole("link", { name: "Download" }).getAttribute("href") as string);
    expect(download.status()).toBe(200); expect(download.headers()["content-disposition"]).toContain("attachment");
    expect(download.headers()["x-content-type-options"]).toBe("nosniff"); expect(download.headers()["cache-control"]).toBe("private, no-store");
    expect(await download.text()).toBe(marker);

    await page.goto(`${webUrl}/dashboard`); await page.getByRole("button", { name: "Sign out" }).click();
    await login(page, appAdminEmail!, appAdminPassword!); await page.goto(`${webUrl}/documents`);
    await expect(page.getByText(/Document [0-9a-f]{8}/)).toBeVisible();
    await expect(page.getByText("Browser runbook")).toHaveCount(0); await expect(page.getByRole("link", { name: "Download" })).toHaveCount(0);
    await page.goto(`${webUrl}/dashboard`); await page.getByRole("button", { name: "Sign out" }).click();
    await login(page, ownerEmail!, ownerPassword!); await page.goto(`${webUrl}/documents`);
    page.once("dialog", dialog => dialog.accept()); await page.getByRole("button", { name: "Archive" }).click();
    await expect(page.getByRole("status")).toHaveText("Document archived"); await page.getByRole("button", { name: "Restore" }).click();
    await expect(page.getByRole("status")).toHaveText("Document restored");
    page.once("dialog", dialog => dialog.accept()); await page.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByRole("status")).toHaveText("Document deleted");
    const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, url: location.href }));
    expect(JSON.stringify(storage)).not.toContain(marker); expect(JSON.stringify(storage)).not.toContain(filename);
    expect(observed.join("\n")).not.toContain(marker); expect(observed.join("\n")).not.toContain(filename);
  } finally { fs.rmSync(uploadPath, { force: true }); }
});
