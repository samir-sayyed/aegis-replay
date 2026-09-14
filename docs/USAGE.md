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

## Fork and secret boundary

Use `pull_request`, never `pull_request_target`, for fork checks. The supplied
fork workflow checks out fork code without credentials and invokes a commit-pinned
Aegis action from trusted repository history; it runs every committed approved
antibody. Jira and LiteLLM credentials belong only in protected
`aegis-maintainers` environment secrets. Run live integrations only through
`Aegis maintainer integrations` workflow dispatch after configuring that
environment's required reviewers.
Retain CI-uploaded manifests for 90 days.

## Release maintainers

Before first release, create `aegis-replay` project on PyPI, then add trusted
publisher with owner `samir-sayyed`, repository `aegis-replay`, workflow
`.github/workflows/release.yml`, and environment left blank. No PyPI API token
is needed. Push an immutable `vX.Y.Z` tag only after GitHub Actions build and
test workflows pass. Release workflow builds, checks, uploads distribution for
90 days, and publishes with OIDC trusted publishing.

Publish only after maintainer confirms PyPI project and trusted publisher
configuration. Consumers install `pipx install aegis-replay==X.Y.Z` and pin
action references to full commit SHAs; never pin branches.
