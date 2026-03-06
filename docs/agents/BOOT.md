# BOOTSTRAPPING AGENTS

## Initialization Sequence
1.  **IDENTITY LOADING:** Read `IDENTITY.md` and load agent profiles.
2.  **SOUL SYNC:** Load constraints from `SOUL.md`.
3.  **MEMORY WARMUP:** Load tenant-specific state from `MEMORY.md`.
4.  **TOOL VERIFICATION:** Verify all required tools are available and permissions are set.

## Cold Start
On a fresh install, agents must run the `BOOT.md` checklist to ensure the environment is ready for local-first execution.
