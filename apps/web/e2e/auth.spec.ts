import { expect, test } from "@playwright/test";

const email = process.env.IC005_E2E_EMAIL;
const password = process.env.IC005_E2E_PASSWORD;
const browserPath = process.env.IC005_BROWSER_PATH;

test.use({ launchOptions: browserPath ? { executablePath: browserPath } : undefined });

test("two tabs recover login and logout from shared-cookie CSRF rotation", async ({ page, context }) => {
  test.skip(!email || !password, "Temporary native-MySQL E2E credentials are required");
  const csrfResponses: string[] = [];
  const csrfFailures: string[] = [];
  const observe = (response: { url(): string; status(): number; ok(): boolean }) => {
    if (response.url().endsWith("/api/v1/auth/csrf") && response.ok()) csrfResponses.push(response.url());
    if (response.status() === 403 && response.url().includes("/api/v1/auth/")) csrfFailures.push(response.url());
  };
  page.on("response", observe);
  const secondTab = await context.newPage();
  secondTab.on("response", observe);

  await page.goto("http://localhost:3000/dashboard");
  await expect(page).toHaveURL("http://localhost:3000/login");
  await secondTab.goto("http://localhost:3000/login");
  await secondTab.getByLabel("Email address").fill(email!);
  await secondTab.getByLabel("Password").fill("intentionally-wrong");
  await secondTab.getByRole("button", { name: "Sign in" }).click();
  await expect(secondTab.getByText("Email or password is incorrect.", { exact: true })).toBeVisible();

  await page.getByLabel("Email address").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("http://localhost:3000/dashboard");
  await expect(page.getByText(email!, { exact: true })).toBeVisible();
  await expect(page.getByText("Not yet available").first()).toBeVisible();

  await secondTab.getByLabel("Password").fill(password!);
  await secondTab.getByRole("button", { name: "Sign in" }).click();
  await expect(secondTab).toHaveURL("http://localhost:3000/dashboard");
  await expect(secondTab.getByText(email!, { exact: true })).toBeVisible();

  const cookiesAfterLogin = await context.cookies("http://localhost:8000");
  expect(cookiesAfterLogin.some((cookie) => cookie.name === "sessionid" && cookie.httpOnly)).toBe(true);
  expect(cookiesAfterLogin.some((cookie) => cookie.name === "csrftoken" && !cookie.httpOnly)).toBe(true);
  expect(csrfResponses.length).toBeGreaterThanOrEqual(4);

  await secondTab.reload();
  await expect(secondTab.getByText(email!, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL("http://localhost:3000/login");
  await page.goto("http://localhost:3000/dashboard");
  await expect(page).toHaveURL("http://localhost:3000/login");
  await secondTab.goto("http://localhost:3000/dashboard");
  await expect(secondTab).toHaveURL("http://localhost:3000/login");
  expect(csrfFailures.length).toBeGreaterThanOrEqual(2);
});
