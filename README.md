# Aegis Replay

**Aegis Replay prevents known regressions from returning.** It turns a resolved bug into a small, verified record—an *antibody*—then, on later pull requests, runs only antibodies relevant to changed code.

It is technology-neutral. Aegis invokes project-owned commands and reads JUnit XML, so it can protect web frontends, APIs, Python, Java/Kotlin, Android, iOS, and other stacks that can emit JUnit-compatible results.

> Status: early MVP. Pin trusted commits in CI. Package publishing has not yet been configured; install from an exact commit for now.

## Why Aegis exists

Teams fix an incident, add a test, and move on. Months later, a seemingly unrelated pull request changes same area and reintroduces it. Running whole test suite for every change is slow; relying on developer memory is unreliable.

Aegis makes past incidents reusable protection:

1. Record invariant that must always remain true, affected files, and exact regression test.
2. Prove test detects known-bad and alternate-bad implementations while fixed implementation passes.
3. Require review approval for proof record.
4. On PR, match changed paths and symbols to approved antibodies.
5. Run only selected regression tests, then show why check ran and why it failed.

An antibody is not an AI-generated test. It is audited evidence that an existing test catches a specific class of regression.

## Core concepts

| Term | Meaning |
| --- | --- |
| **Invariant** | Plain-language behavior that must not break, e.g. “public catalog never exposes internal products.” |
| **Antibody** | Repository-local JSON record linking invariant, scope, test identity, proof inputs, and approval. |
| **Proof** | Isolated execution of known-bad, fixed, alternate-bad, and control states. |
| **Guard** | PR-time command that selects approved antibodies and runs focused tests. |
| **Selection manifest** | Sanitized, hashed audit record of what was selected and why. |

## Requirements

- Python 3.11 or later
- Git repository
- Existing test command that writes JUnit XML
- CI runner with runtime needed by project (Node, Java, Xcode, Python, etc.)
- GitHub CLI (`gh`) only when verifying a real GitHub approval

## Install

### Local development

```bash
git clone https://github.com/samir-sayyed/aegis-replay.git
cd aegis-replay
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest
aegis --help
```

### Consumer project

Until first PyPI release, install exact trusted commit:

```bash
python -m pip install 'git+https://github.com/samir-sayyed/aegis-replay.git@<full-40-character-commit-sha>'
```

After release, prefer pinned version:

```bash
pipx install aegis-replay==<version>
```

Never point CI at moving branch such as `main`.

## Quick start

Run commands from protected repository root.

### 1. Create configuration

```bash
aegis init
```

This creates `aegis.yaml`. Replace starter command with your test runner. Commands are argv arrays, never shell strings; this prevents shell injection and makes execution reproducible.

Example for TypeScript/Jest:

```yaml
schema_version: 1
targets:
  - name: web-unit
    runner: jest-junit
    command: [npm, test, --, --runInBand]
    junit_xml: reports/junit.xml
    directory: typescript-jest
    scope: [typescript-jest/src]
```

Example for Python/pytest:

```yaml
schema_version: 1
targets:
  - name: api-unit
    runner: pytest-junit
    command: [python, -m, pytest, --junitxml=reports/junit.xml]
    junit_xml: reports/junit.xml
    scope: [src]
```

Supported runner presets: `command-junit`, `pytest-junit`, `jest-junit`, `gradle-junit`, and `xcode-junit`.

### 2. Verify test output

```bash
aegis doctor --target web-unit
```

`doctor` runs configured command, verifies JUnit XML location, and checks result can safely identify individual test cases. Fix this before creating any antibody.

### 3. Create antibody

Create narrowly scoped record after regression test exists:

```bash
aegis antibody create catalog-privacy \
  --invariant 'Public catalog filtering never exposes internal products.' \
  --target web-unit \
  --test 'public product catalog#never exposes internal products in a public category' \
  --scope typescript-jest/src/filter.ts \
  --proof-input known_bad_mutation_sha256=<sha256-of-known-bad-patch>
```

Records live in `.aegis/antibodies/`. Commit them with regression test and mutation files. Do not include credentials, customer data, raw incident reports, or unredacted diffs.

### 4. Prove it

Proof runs three isolated Git states plus control check:

```bash
aegis prove catalog-privacy \
  --known-bad .aegis/mutations/catalog-privacy-known-bad.diff \
  --alternate-bad .aegis/mutations/catalog-privacy-alternate-bad.diff \
  --control 'public product catalog#returns an empty list when category is unknown'
```

Expected result:

```text
Aegis proof: verified .aegis/proofs/catalog-privacy.json
```

- known-bad: chosen regression test must fail
- repaired/current state: regression test must pass
- alternate-bad: same test must fail for another realistic broken implementation
- control: unrelated valid behavior must pass

This prevents false confidence from tests that always pass or are too broad.

### 5. Approve proof

Use real GitHub review. Required owner must be non-placeholder reviewer identity accepted by your policy:

```bash
aegis approve catalog-privacy \
  --github-repository your-org/your-repository \
  --pull-number 123 \
  --required-owner reviewer@your-company.com
```

For local deterministic testing only, use recorded GitHub fixture:

```bash
aegis approve catalog-privacy \
  --github-fixture .aegis/fixtures/catalog-privacy-review.json \
  --required-owner reviewer@your-company.com
```

### 6. Run selected protection

```bash
aegis guard --changed typescript-jest/src/filter.ts
aegis antibody explain catalog-privacy
```

## PR integration with GitHub Actions

Use `pull_request`, never `pull_request_target`, for untrusted PR code. This job obtains changed paths and runs Aegis:

```yaml
name: Aegis PR guard

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: read

jobs:
  aegis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false
      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'
      - name: Install Aegis
        run: python -m pip install 'git+https://github.com/samir-sayyed/aegis-replay.git@<full-40-character-commit-sha>'
      - id: changed
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh api --paginate "repos/${GITHUB_REPOSITORY}/pulls/${{ github.event.pull_request.number }}/files?per_page=100" --jq '.[].filename' > changed-paths.txt
          {
            echo 'paths<<EOF'
            cat changed-paths.txt
            echo EOF
          } >> "$GITHUB_OUTPUT"
      - name: Replay relevant regressions
        run: |
          args=(guard --directory .)
          while IFS= read -r path; do args+=(--changed "$path"); done <<< "${{ steps.changed.outputs.paths }}"
          aegis "${args[@]}"
```

For consumer action integration, pin full immutable commit SHA:

```yaml
- uses: samir-sayyed/aegis-replay@<full-40-character-commit-sha>
  with:
    changed-paths: ${{ steps.changed.outputs.paths }}
```

Upload `.aegis/manifests/*.json` as CI artifacts; recommended retention is 90 days.

### Fork PRs

Fork code must never receive Jira, LiteLLM, deployment, signing, or publishing credentials. For fork PRs, run committed approved antibodies without secrets:

```yaml
if: ${{ github.event.pull_request.head.repo.fork }}
```

Use `aegis guard --all` or action’s `changed-paths: '*'` for this path.

## Selection behavior

Default selection is deterministic and lexical:

1. Direct scope/path or declared symbol match wins.
2. Remaining candidates are ranked with BM25-style lexical relevance over invariant, scope, and sanitized Jira intent.
3. `aegis guard` runs selected approved, fresh antibodies.

Preview ranking and produce audit manifest:

```bash
aegis select --changed typescript-jest/src/filter.ts --manifest
```

Optional LiteLLM semantic selection is additive, not authority. If model is unavailable, malformed, unsafe, or uncertain, Aegis falls back safely rather than skipping candidate coverage:

```bash
export LITELLM_BASE_URL=https://your-litellm.example/v1
export LITELLM_MODEL=your-approved-model
export LITELLM_API_KEY=...
aegis select --changed typescript-jest/src/filter.ts \
  --semantic --commit "$GITHUB_SHA" --manifest
```

Do not run live semantic selection inside untrusted PR workflow. Use protected, maintainer-only workflow or locally controlled environment.

## Jira intent context

Jira helps selection understand fix intent; it does not replace test proof. Capture only allowed, sanitized fields and link result to antibody:

```bash
export JIRA_EMAIL=maintainer@your-company.com
export JIRA_API_TOKEN=...
aegis jira capture \
  --key APP-42 \
  --jira-url https://your-company.atlassian.net \
  --antibody catalog-privacy \
  --acceptance-field customfield_12345
```

For testable local setup, pass `--jira-fixture path/to/sanitized-response.json` instead. Comments and attachments are intentionally excluded.

## What gets committed

```text
aegis.yaml
.aegis/antibodies/<id>.json
.aegis/proofs/<id>.json
.aegis/approvals/<id>.json
.aegis/mutations/<id>-*.diff
.aegis/jira/<key>.json              # sanitized only, when used
.aegis/jira-links/<id>.json         # when used
```

Never commit `JIRA_API_TOKEN`, `LITELLM_API_KEY`, raw Jira comments or attachments, unrestricted ticket payloads, or raw PR diffs supplied to semantic selection.

## Debugging

| Symptom | Check |
| --- | --- |
| `doctor` fails | Confirm command works locally, JUnit XML is generated at configured relative path, and test identities are unique. |
| Guard selects nothing | Confirm changed path overlaps antibody `scope`, then inspect `aegis select --changed <path> --manifest`. |
| Guard rejects antibody | Run `aegis antibody explain <id>`; proof may be stale because source, config, tests, mutation, Jira context, parser, or schema changed. |
| Approval fails | Ensure reviewer is real, approval belongs to proof source revision, and required owner matches policy. |
| Semantic selection unavailable | Expected safe behavior: Aegis falls back rather than silently omitting candidates. |

## Demo repository

See [aegis-replay-poc](https://github.com/samir-sayyed/aegis-replay-poc) for lightweight web/Jest demonstration. It includes intentionally broken PR scenario where focused Aegis check explains that catalog change exposes internal item; restoring visibility filter makes same PR check pass.

## Security model

- Config permits only explicit argv commands and safe relative paths.
- Approved proof is invalidated when relevant proof inputs change.
- PR jobs use least privilege and do not persist checkout credentials.
- Fork PRs run without secrets.
- Jira snapshot is allowlisted and sanitized.
- Semantic inputs are hashed in manifests; raw diffs are not stored.
- Pin every third-party action and Aegis reference to immutable full commit SHA in production.

## Roadmap

- Publish first version to PyPI with trusted publishing.
- Extend turnkey adapters and examples across Android, iOS, backend, and frontend projects.
- Add richer PR annotations and dashboard/reporting integrations.

## License

Apache-2.0. See [LICENSE](LICENSE).
