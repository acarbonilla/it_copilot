import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const adminEmail = process.env.F02_E2E_ADMIN_EMAIL;
const adminPassword = process.env.F02_E2E_ADMIN_PASSWORD;
const mailbox = process.env.F02_E2E_MAILBOX;
const browserPath = process.env.F02_E2E_BROWSER_PATH;

test.use({ launchOptions: browserPath ? { executablePath: browserPath } : undefined });

test("fragment invitation activates in a real browser and legacy token paths are rejected", async ({ page }) => {
  test.skip(!adminEmail || !adminPassword || !mailbox, "F02 isolated E2E environment is required");
  const invitee = `fragment-${Date.now()}@example.test`;
  const password = "unique-browser-passphrase-4829";
  const observed: string[] = [];
  page.on("request", request => observed.push(request.url()));
  page.on("console", message => observed.push(message.text()));

  await page.goto("http://localhost:3000/login");
  await page.getByLabel("Email address").fill(adminEmail!);
  await page.getByLabel("Password").fill(adminPassword!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("http://localhost:3000/dashboard");
  await page.goto("http://localhost:3000/admin/users");
  await page.getByLabel("Email").fill(invitee);
  await page.getByRole("button", { name: "Invite user" }).click();
  await expect(page.getByRole("status")).toHaveText("Invitation created");

  const findArtifact = () => fs.readdirSync(mailbox!).find(file => {
    if (!file.endsWith(".json")) return false;
    return (JSON.parse(fs.readFileSync(path.join(mailbox!, file), "utf8")) as { recipient: string }).recipient === invitee;
  });
  await expect.poll(findArtifact).toBeTruthy();
  const artifact = path.join(mailbox!, findArtifact()!);
  const delivery = JSON.parse(fs.readFileSync(artifact, "utf8")) as { recipient: string; activation_url: string };
  expect(delivery.recipient).toBe(invitee);
  const token = delivery.activation_url.split("#token=")[1];
  expect(token).toMatch(/^[A-Za-z0-9_-]{43}$/);

  await page.goto(delivery.activation_url);
  await expect.poll(() => page.evaluate(() => location.hash)).toBe("");
  expect(page.url()).toBe("http://localhost:3000/activate");
  await page.getByLabel("Create password").fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Activate account" }).click();
  await expect(page).toHaveURL("http://localhost:3000/login");
  expect(observed.join("\n")).not.toContain(token);

  const legacyToken = "L".repeat(43);
  const response = await page.goto(`http://localhost:3000/activate/${legacyToken}`);
  expect(response?.status()).toBe(404);
  expect(await page.content()).not.toContain(legacyToken);
});
