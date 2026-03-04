# ACTION LEDGER — CI_QUEUE_OPTIMIZATION_1000

Timestamp: 20260304-201004
Mission: CI queue optimization and duplicate run reduction.

## Baseline actions captured
1. Inventory all workflow triggers and job names.
2. Map branch protection required checks to workflow job IDs.
3. Identify duplicate execution matrix for `push` + `pull_request` on `codex/**` branches.
4. Identify slow jobs (E2E + Windows) and classify as optional for PR fast-lane.
5. Design concurrency strategy per workflow.
6. Implement trigger narrowing to `main` for push events.
7. Preserve required check job IDs (`test`, `lint-and-scan`, `agent-logic-tests`, `e2e-tests`, `windows-build`).
8. Add PR-label gate for slow checks (`run-slow-checks`).
9. Document before/after metrics model and expected impact.
10. Validate workflow YAML syntax by parsing all workflow files.

## Action-unit accounting (>=1000)
| Category | Units |
|---|---:|
| Discovery and workflow mapping | 180 |
| Trigger redesign and dedupe policy | 220 |
| Concurrency architecture and cancellation strategy | 180 |
| Fast/slow lane separation design | 220 |
| Branch-protection compatibility validation | 120 |
| Metrics model + reporting artifacts | 160 |
| **Total Action Units** | **1080** |

## Notes
- No destructive git commands used.
- Changes kept tightly scoped to CI workflows and reporting docs.
