# Aegis Replay MVP

Install locally with `pipx install .` during development, or pin a published
release in adoption workflows. Never use an unpinned branch reference for CI.

Run `aegis init`, configure argv-only `command-junit` targets, then use
`aegis doctor` to verify exact JUnit output. Create a local antibody, prove it
against known-bad, fixed, and alternate-bad worktrees, and verify GitHub review
approval before using guards.

Jira snapshots accept only sanitized ticket metadata and agreed intent fields;
comments and attachments are excluded. LiteLLM selection is additive: failed,
unsafe, unavailable, or uncertain semantic selection runs all candidates.

Selection manifests contain hashes, rankings, decisions, model/prompt identity,
and fallback state. Do not store secrets, raw diffs, or unsanitized Jira data.
Retain CI-uploaded manifests for 90 days.

Fork PRs run under `pull_request` with read-only permissions and `guard --all`.
They never receive Jira, model, signing, or deployment secrets; live integrations
are maintainer-dispatched only. Quiet Hours migration is intentionally outside
this MVP.
