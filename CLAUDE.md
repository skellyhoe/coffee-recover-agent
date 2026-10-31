# Rules
- All data, product names and codes are invented. Never use real endpoints, keys, vendor names or
  code from any other repo (NDA). Call the systems "vendor API" and "ledger".
- The system is fully simulated. Never describe the agent as running in production. The real job
  today only detects, holds back and alerts; this agent is new, built for the hackathon.
- No confirm-invoice capability may exist anywhere. The ledger sim has no confirm endpoint, and a
  test proves it. Limits are enforced in code, not in prompts.
- Deterministic code does matching and verifying; the LLM investigates, decides and explains.
- Everything the agent changes must be reviewable and undoable.
- Prefer a working, demoable slice over completeness. Run tests before saying anything is done.
  Commit after each step.
