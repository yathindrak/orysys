# Orysys release checklist

Use one exact commit for CI, live evidence, and the recording. Do not paste secrets,
raw tokens, `.env` content, restricted excerpts, or approval tokens into any artifact.

## Repository gates

- [ ] `uv sync --locked --all-groups`
- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy src`
- [ ] `uv run pytest`
- [ ] `uv run python -m orysys.evals.answers`
- [ ] `uv run python -m orysys.evals.controls`
- [ ] `uv run python -m orysys.evals.reliability`
- [ ] `docker compose config -q`
- [ ] CI `test`, `migrations`, `supply-chain`, and `container-smoke` jobs pass

## Release identity

- Final commit: `________________`
- Public repository: `________________`
- CI run: `________________`
- Corpus version: `bank-demo-v1` or `________________`
- Prompt version: `direct-answer-v1` or `________________`
- Chat model: `________________`
- Embedding model and dimensions: `________________`

## Live evidence

- [ ] Direct-answer trace: `________________`
- [ ] Annual-research trace: `________________`
- [ ] Authorized MCP/analytics trace: `________________`
- [ ] Controlled-degradation trace: `________________`
- [ ] Approval/decision trace: `________________`
- [ ] Trace metadata is redacted and matches the final commit/configuration
- [ ] Optional selective judge report captured without replacing deterministic gates

## Walkthrough and publication

- [ ] Follow [`demo-script.md`](demo-script.md) within 45 minutes
- [ ] Show viewer denial, analyst tool success, and administrator approval
- [ ] Show direct citations, bounded research, memory lifecycle, feedback, and limits
- [ ] Show the exact commit and matching CI result
- [ ] Recording reviewed for accidental credential or personal-data exposure
- Recording URL: `________________`
- [ ] Update [`release-audit.md`](release-audit.md) from Implemented to Verified only for
      rows whose automated and walkthrough evidence now agree
- [ ] Create the release tag from the demonstrated commit
