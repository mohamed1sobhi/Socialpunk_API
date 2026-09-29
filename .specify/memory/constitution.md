<!--
Sync Impact Report
- Version change: unratified template -> 1.0.0
- Modified principles:
  - Placeholder principles 1-5 -> I. Engineering Guidelines Are Authoritative
- Added sections:
  - Authority and Scope
  - Development Workflow and Compliance
- Removed sections:
  - Four unused placeholder principle slots
- Templates reviewed:
  - ✅ .specify/templates/plan-template.md - updated with reference-only compliance gates
  - ✅ .specify/templates/spec-template.md - no update required
  - ✅ .specify/templates/tasks-template.md - updated with reference-only governance guidance
  - ✅ .specify/templates/constitution-template.md - no update required
- Installed Spec Kit commands reviewed:
  - ✅ .agents/skills/speckit-*/SKILL.md - no stale agent-specific references found
- Follow-up TODOs: None
-->
# socialpunk Social Media API Constitution

## Core Principles

### I. Engineering Guidelines Are Authoritative

[`engineering-guidelines.md`](../../engineering-guidelines.md) is the sole source of truth for
this project's architecture, coding constraints, design contracts, and engineering rules.
Anyone creating or reviewing a specification, plan, task list, implementation, migration, or
technical documentation MUST read and comply with its current contents. Other project artifacts
MUST reference applicable guideline sections instead of copying or paraphrasing their rules. If an
artifact conflicts with the guidelines, the guidelines prevail and the conflicting artifact MUST
be corrected.

Rationale: keeping engineering policy in one authoritative file prevents drift and makes every
rule change reviewable in one place.

## Authority and Scope

This constitution governs how Spec Kit artifacts and development work consume the engineering
guidelines. It does not define, duplicate, or extend the project's technical architecture.

- `AGENTS.md` is a discovery pointer to `engineering-guidelines.md`, not an independent rule source.
- Feature specifications define required behavior and outcomes; plans and tasks define scoped
  implementation work. None may override the engineering guidelines.
- Project-wide architecture or engineering-rule changes MUST be made in
  `engineering-guidelines.md` first. Dependent artifacts may then be updated by reference.

## Development Workflow and Compliance

- Before planning, task generation, implementation, convergence analysis, or code review, the
  current constitution and `engineering-guidelines.md` MUST be read.
- Every implementation plan's Constitution Check MUST identify the applicable guideline sections
  by reference and record whether the design complies; it MUST NOT reproduce the rules.
- Generated tasks MUST remain traceable to the feature specification and plan. When a task depends
  on an engineering constraint, it MUST cite the relevant guideline section rather than restating
  that constraint.
- Any unresolved conflict with `engineering-guidelines.md` blocks implementation until the
  conflicting artifact is corrected or the authoritative guideline is explicitly amended.

## Governance

This constitution controls governance of the single-source policy; it does not supersede
`engineering-guidelines.md` on engineering or architecture matters.

Amendments to this constitution MUST document the reason, semantic version change, amendment date,
and synchronization impact on dependent Spec Kit templates. Changes to project architecture or
engineering rules belong exclusively in `engineering-guidelines.md`, not in this constitution.

Constitution versions follow semantic versioning:

- MAJOR: changes the authoritative source, precedence, or core governance model.
- MINOR: adds or materially expands a governance obligation or compliance gate.
- PATCH: clarifies wording without changing governance requirements.

Plan and implementation reviews MUST verify compliance with both this constitution and the current
engineering guidelines. Non-compliance requires correction before the affected work is considered
complete.

**Version**: 1.0.0 | **Ratified**: 2026-07-22 | **Last Amended**: 2026-07-22
