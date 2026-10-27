# IT Support Copilot

IT Support Copilot is a Next.js and Django monorepo. IC-002 implements the initial Django/DRF API and native-MySQL health check while preserving the custom-user migration boundary for IC-003.

## Repository layout

| Path | Ownership |
| --- | --- |
| `apps/web` | Next.js, TypeScript, Tailwind CSS, and shadcn/ui frontend (future task) |
| `apps/api` | Django REST Framework HTTP API (IC-002 and later) |
| `workers/document_processor` | Separate document-worker entrypoint using shared Django business logic (future task) |
| `packages/api-contract` | Generated/shared API contract artifacts (future task) |
| `infra/local` | Local-development infrastructure notes and extensions |
| `tests/e2e` | Cross-service end-to-end tests |
| `docs` | Product, architecture, API, module, and TTDM task records |

Placeholder directories contain a `README.md` so their intended ownership is tracked without pretending a framework has been initialized.

## Prerequisites

- Git 2.45 or newer
- Node.js 22 LTS or 24 LTS and npm 10 or newer (repository validation)
- Python 3.12 or 3.13
- An existing native MySQL installation for API development; Docker Compose remains optional

Windows 11 with PowerShell 7, current macOS, and current Linux distributions are intended development environments. IC-001 was authored on Windows; clean-checkout verification on every platform is still pending.

## Setup

```shell
git clone <repository-url> it-support-copilot
cd it-support-copilot
git switch feature/IC-001-monorepo-setup
```

Create a private environment file:

```shell
cp .env.example .env
```

On PowerShell, use `Copy-Item .env.example .env`. The committed values are development placeholders. Change passwords and `DJANGO_SECRET_KEY` in `.env`; never commit that file.

No npm dependencies are required for IC-001. Validate the repository with:

```shell
npm run validate
docker compose config --quiet
```

To start the optional local MySQL container:

```shell
docker compose up -d db
docker compose ps
```

Stop it with `docker compose down`. Add `--volumes` only when you intentionally want to erase local database data.

## API setup

Native Windows setup, database account creation, migrations, and startup commands are documented in [apps/api/README.md](apps/api/README.md). Docker is not required.

## Current limitations

- `apps/web`, the document worker, contracts, and end-to-end tests remain future-task boundaries.
- Compose defines MySQL only. API and web services must be added by their approved task codes.
- The database credentials in `.env.example` are deliberately non-production placeholders.
- Authentication, document processing, retrieval, and OpenAI integration remain out of IC-002 scope.

See the [documentation index](docs/README.md) and [IC-001 verification record](docs/tasks/IC-001/test-results.md).

