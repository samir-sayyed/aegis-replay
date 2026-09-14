# aegis-replay
Portable regression-proof and semantic CI guard for any technology stack

See [adoption guide](docs/USAGE.md). Aegis records regression invariants
locally, proves known-bad/fixed/alternate-bad states, requires canonical
approval, then reruns relevant coverage on pull requests.

Install released versions with `pipx install aegis-replay==0.1.0`.

Pin reusable action to full immutable commit SHA:

```yaml
uses: samir-sayyed/aegis-replay@<full-40-character-commit-sha>
```

Never give fork PR jobs Jira, LiteLLM, signing, deployment, or PyPI credentials.
