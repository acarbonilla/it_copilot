import { expect, test } from "@playwright/test";

const email = process.env.IC005_E2E_EMAIL;
const password = process.env.IC005_E2E_PASSWORD;
const browserPath = process.env.IC005_BROWSER_PATH;

test.use({ launchOptions: browserPath ? { executablePath: browserPath } : undefined });

test("real browser session login, refresh, CSRF rotation, logout, and access denial", async ({ page, context }) => {
  test.skip(!email || !password, "Temporary native-MySQL E2E credentials are required");
  const csrfResponses: string[] = [];
  page.on("response", (response) => {
    if (response.url().endsWith("/api/v1/auth/csrf") && response.ok()) csrfResponses.push(response.url());
  });

  await page.goto("http://localhost:3000/dashboard");
  await expect(page).toHaveURL("http://localhost:3000/login");
  await page.getByLabel("Email address").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("http://localhost:3000/dashboard");
  await expect(page.getByText(email!, { exact: true })).toBeVisible();
  await expect(page.getByText("Not yet available").first()).toBeVisible();

  const cookiesAfterLogin = await context.cookies("http://localhost:8000");
  expect(cookiesAfterLogin.some((cookie) => cookie.name === "sessionid" && cookie.httpOnly)).toBe(true);
  expect(cookiesAfterLogin.some((cookie) => cookie.name === "csrftoken" && !cookie.httpOnly)).toBe(true);
  expect(csrfResponses.length).toBeGreaterThanOrEqual(2);

  await page.reload();
  await expect(page.getByText(email!, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL("http://localhost:3000/login");
  await page.goto("http://localhost:3000/dashboard");
  await expect(page).toHaveURL("http://localhost:3000/login");
});
