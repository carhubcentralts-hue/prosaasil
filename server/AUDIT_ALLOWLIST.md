# Server pip-audit Allowlist

This file documents known pip-audit findings that have been reviewed and accepted.

## Policy

- **high/critical** vulnerabilities **block** CI — no exceptions without documented justification below.
- `pip-audit` runs as a blocking step in CI (`continue-on-error: false`).
- If a vulnerability is a false positive or only affects unused code paths, it is documented here.

## Current Allowlist

_No allowlisted vulnerabilities at this time._

## Review Schedule

- Reviewed monthly as part of dependency update cycle.
- Last reviewed: 2026-02-06
