# kritva-sense

Kritva Sense: part of Kritva OS V2, planned and tracked from [kritva-program](https://github.com/KritvaOS/kritva-program).

**Status:** planning and governance baseline only. There is no implementation yet; the first task (KOS-SENSE-001, Sense architecture and data contract) is proposed and not yet approved.

## Scope

Owns: sensor identity, timestamps, units, frame and coordinate conventions, validity and stale-data behaviour, errors and versioning of the Sense data contract and its reference validation.

Does not own: motion commands (kritva-motion), inference (kritva-mind), skill orchestration (kritva-skill), device drivers below the contract, and the platform foundation (kritva-core).

Depends on: kritva-core (approved contract), kritvaos-community (public architecture description).

## Layout

| Path | Purpose |
|---|---|
| [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) | Acceptance criteria and test gates |
| [planning/](planning/) | Tasks, milestones, review checklist, commit step, changelog |
| [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) | Rules for contributors, agents and vulnerability reporting |
| [Makefile](Makefile) | Standard check targets (unimplemented gates report NOT_IMPLEMENTED, never pass) |
| `.github/` | CODEOWNERS and the secret-scan and commit-message-check workflows |

Source folders are added only when the first real task needs them.

## Checks

```bash
make check   # planning files present, commit-checker self-test
make test    # reports NOT_IMPLEMENTED (exit 3) until tests exist
```

## Program alignment

Milestones: V2-M0-SENSE-001 (governance baseline), V2-M1-SENSE-001 (contract), V2-M2-SENSE-001 (validation). Dates are proposed in kritva-program `v2/planning/` and are not approved. Nothing in this repository adds baseline weight or credit.
