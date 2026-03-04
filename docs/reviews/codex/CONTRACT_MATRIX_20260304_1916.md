# CONTRACT_MATRIX_20260304_1916

## Scope
- TOOL_CONTRACT_1000 quick-pass for standardized `summary/health` endpoints.
- Validation focus: dashboard aggregation contract + chatbot payload alias contract.

## Standard Endpoint Matrix
| Tool | `/api/<tool>/summary` | `/api/<tool>/health` | Notes |
|---|---|---|---|
| dashboard | ✅ | ✅ | Aggregates only via `/api/dashboard/tool-matrix` |
| upload | ✅ | ✅ | |
| projects | ✅ | ✅ | |
| tasks | ✅ | ✅ | |
| messenger | ✅ | ✅ | |
| email | ✅ | ✅ | |
| calendar | ✅ | ✅ | |
| time | ✅ | ✅ | |
| visualizer | ✅ | ✅ | Legacy `POST /api/visualizer/summary` remains domain action endpoint |
| settings | ✅ | ✅ | |
| chatbot | ✅ | ✅ | Declares canonical request aliases (`message/msg/q`) |
| kalender | ✅ | ✅ | Domain contract builders |
| aufgaben | ✅ | ✅ | Domain contract builders |
| zeiterfassung | ✅ | ✅ | Domain contract builders |
| projekte | ✅ | ✅ | Domain contract builders |
| einstellungen | ✅ | ✅ | Domain contract builders |

## Dashboard/Chatbot Payload Consistency
- Dashboard summary now declares `matrix_endpoint` and `aggregate_mode=summary_only`.
- Chatbot summary now declares `payload_contract.request_fields=[message,msg,q]` and expected response keys `[ok,response]`.

## Gaps / Priorities
- P0: `scripts/ops/healthcheck.sh` cannot run unit tests in this container because `pytest` is unavailable on `python3`.
- P1: Massive-output requirement (`>=1000` ledger actions) not realistically completable within one short agent cycle; partial ledger delivered for traceability.
