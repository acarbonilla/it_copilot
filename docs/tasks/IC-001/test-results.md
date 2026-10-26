# IC-001 test results

**Date:** 2026-10-26  
**Environment:** Windows with PowerShell; Git 2.45.2.windows.1; Node.js 20.11.1; Python 3.13.5; Docker unavailable.

## Results

| Check | Status | Evidence |
| --- | --- | --- |
| Initial repository audit | Pass | Workspace was empty and not initialized as Git; no changes existed to overwrite. |
| Feature branch | Pass | `git -c safe.directory=... branch --show-current` returned `feature/IC-001-monorepo-setup`. The override is needed because the sandbox and workspace owner are different Windows identities. |
| Repository structure | Pass | PowerShell equivalent of the validator found all 19 required paths. |
| Project `npm run validate` command | Blocked | Installed Node.js 20.11.1 is below the documented supported minimum, and sandbox path resolution failed with `EPERM` at `C:\Users\dc`. |
| JSON syntax (`package.json`) | Pass | Node `JSON.parse` completed and printed `package.json JSON passed`. |
| Compose YAML syntax | Pass | Python/PyYAML `yaml.safe_load` parsed `compose.yaml`. |
| Docker Compose semantic validation | Not Run | Docker/Compose is not installed in the implementation environment. `docker` returned `CommandNotFoundException`. |
| Git changed-file inspection | Pass | Status showed only the IC-001 root configuration and the new boundary/documentation directories. |
| Candidate-file secret-pattern inspection | Pass | Ripgrep found no OpenAI key, AWS access-key, or private-key-header patterns outside `.git`; `.env` was confirmed ignored by `.gitignore:2`. |
| Documentation link targets | Pass | Every local file linked by `docs/README.md` exists. |
| README local walkthrough | Pass | Commands, PowerShell environment-copy alternative, limitations, and directory names were checked against the workspace. Runtime startup was not claimed. |
| Clean-clone walkthrough | Not Run | Requires a committed remote checkout. This remains acceptance evidence for review/PR validation. |
| Cross-platform setup | Not Run | No macOS/Linux environment is available in this implementation session. |
| Application lint/runtime tests | Not Run | No application runtime exists in IC-001. |

## Acceptance mapping

| Criteria | Verification |
| --- | --- |
| AC-01, AC-06, AC-09 | Pass: structure and documentation records exist. |
| AC-02 | Pass: root README documents prerequisites, setup, environment, layout, validation, and limitations. |
| AC-03 | Pass: candidate files passed pattern inspection and `.env` is ignored. A post-commit tracked-file scan remains appropriate during review. |
| AC-04 | Partial: JSON and YAML syntax passed; Docker semantic validation and the supported-Node project command were not run. |
| AC-05 | Partial: local documentation walkthrough passed; clean supported-environment checkout is Not Run. |
| AC-07, AC-08 | Pass: initial workspace was empty and final status is confined to IC-001 structure/configuration/documentation. |
| AC-10 | Pass as a safeguard: review remains pending and the task is neither merged nor marked Completed. |

## Review blockers

AC-04 and AC-05 cannot be fully accepted from this environment. Before approval, run `npm run validate` with Node.js 22 or 24, run `docker compose config --quiet`, and perform the README workflow from a clean checkout.

