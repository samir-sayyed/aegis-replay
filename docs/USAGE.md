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

Before first release, configure PyPI Trusted Publishing for this repository and
release workflow. Build distribution with `python -m build`, inspect with
`twine check dist/*`, then publish immutable `vX.Y.Z` release. Consumers pin
package versions and action commits; never pin branches.
