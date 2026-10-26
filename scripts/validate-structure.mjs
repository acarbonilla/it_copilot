import { access, readFile } from "node:fs/promises";

const requiredPaths = [
  ".env.example",
  ".gitignore",
  "README.md",
  "compose.yaml",
  "apps/web/README.md",
  "apps/api/README.md",
  "workers/document_processor/README.md",
  "packages/api-contract/README.md",
  "tests/e2e/README.md",
  "infra/local/README.md",
  "docs/README.md",
  "docs/product/mvp-requirements.md",
  "docs/architecture/overview.md",
  "docs/architecture/data-model.md",
  "docs/changelog.md",
  "docs/tasks/IC-001/specification.md",
  "docs/tasks/IC-001/implementation.md",
  "docs/tasks/IC-001/test-results.md",
  "docs/tasks/IC-001/review.md"
];

const missing = [];
for (const path of requiredPaths) {
  try {
    await access(path);
  } catch {
    missing.push(path);
  }
}

const envExample = await readFile(".env.example", "utf8");
const forbidden = [/sk-[A-Za-z0-9_-]{20,}/, /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/];
const secretFindings = forbidden.filter((pattern) => pattern.test(envExample));

if (missing.length || secretFindings.length) {
  if (missing.length) console.error(`Missing required paths:\n${missing.join("\n")}`);
  if (secretFindings.length) console.error("Potential secret material found in .env.example");
  process.exitCode = 1;
} else {
  console.log(`Structure validation passed (${requiredPaths.length} required paths).`);
  console.log("Basic .env.example secret-pattern check passed.");
}

