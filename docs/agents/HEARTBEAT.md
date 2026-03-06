# AGENT HEARTBEAT AND HEALTH

## Status Check
Agents must report their health status every 5 seconds during active execution:
`[ID: ORCH-ROUTER | HEALTH: OK | TASK: ROUTING_REQUEST_123]`

## Failure Recovery
- **RETRY:** Up to 3 times for transient errors.
- **FAILOVER:** If a worker fails, the TRIAGE agent takes over.
- **PANIC:** In case of safety violation, all execution stops immediately.
