# engineering-intelligence Specification

## MODIFIED Requirements

### Requirement: Project readiness classification

The intelligence layer SHALL classify a repository into one of three readiness gates
— MVP, READY, DONE — from observable signals only, and SHALL report each gate check as
`met`, `missing`, or `unknown`. A check is `unknown` when its signal is not captured by
the repository's indexing mode (e.g. CI/tests when no file tree is indexed) and SHALL
NOT count toward a gate. READY SHALL require CI, tests, a documented design (OpenSpec or
an ADR document), at least one closed issue and one merged pull request, a README, and a
guide document. DONE SHALL require READY plus a dependency manifest, monitoring
(Dependabot or a security-scanning workflow), a SECURITY document, a low open-bug ratio,
and at least one published GitHub Release. The layer SHALL also produce an
organization-level distribution (counts per gate) with each repository's gate and what
it is missing to reach READY.

#### Scenario: Repository meeting all READY checks
- **WHEN** a repository has CI, tests, OpenSpec/ADRs, a closed issue, a merged PR, a README, and a guide doc
- **THEN** it SHALL be classified READY with no missing READY checks

#### Scenario: Unknown signal cannot satisfy a gate
- **WHEN** a repository's indexing mode captures no file tree, so CI/tests are unknown
- **THEN** those checks SHALL be reported `unknown` and the repository SHALL NOT be classified READY on them

#### Scenario: DONE requires observable hardening and a release
- **WHEN** a READY repository additionally has a dependency manifest, monitoring, a SECURITY doc, a low open-bug ratio, and at least one published release
- **THEN** it SHALL be classified DONE

#### Scenario: A release is required for DONE
- **WHEN** a repository meets every other DONE check but has no published release
- **THEN** the `releases` check SHALL be `missing` and the repository SHALL NOT be classified DONE

#### Scenario: Organization distribution
- **WHEN** an organization readiness rollup is requested
- **THEN** it SHALL return per-gate counts and each repository's gate plus its missing-for-READY checks
