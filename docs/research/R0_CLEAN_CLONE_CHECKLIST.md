# SSE R0 — Fresh-clone verification checklist

Run from Git Bash in the committed SSE repository. This creates a separate copy without modifying the source repository.

```bash
BASELINE_DIR="$PWD"
CHECK_DIR="$(mktemp -d)"
git clone --no-local "$BASELINE_DIR" "$CHECK_DIR/sse-clean"
cd "$CHECK_DIR/sse-clean"
git rev-parse HEAD
python -m venv .venv-r0
./.venv-r0/Scripts/python.exe -m pip install -r requirements.txt
./.venv-r0/Scripts/python.exe -m pip check
./.venv-r0/Scripts/python.exe -m compileall -q apps services tools tests
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -v
bash scripts/install-contract-deps.sh
forge build
forge test -vv
git status --short
```

Expected source commit: `45689eaeaac0f4f65b16f3e06e60c0133925ab59`.
Do not interpret a clean-clone test as hosted CI; CI must be checked separately. Do not claim new service-independent or remote multi-VM verification from these local tests. Keep the clean clone's virtualenv and `lib/` dependencies out of Git.

## Result recorded from the 2026-11-09 host transcript

- **Fresh requirements install, dependency check, 106/106 Python tests, Solidity compilation and 35/35 Foundry tests: PASS.**
- **Hosted GitHub Actions CI and explicit displayed clean-clone HEAD/status: pending.**
- See `R0_CLEAN_CLONE_HOST_VALIDATION_2026-11-09.md`.

Run the final checks from the source repository (not the temporary clone):

```bash
git rev-parse HEAD
git status --short
git remote -v
```

For hosted CI, push a reviewed source snapshot to an appropriate authorized GitHub repository, inspect **Actions → CI** and retain the passing run URL and commit SHA. Do not add a fabricated remote or publicly push sensitive files.
