# Global Agent Rules

You are implementing the project in docs/MASTER_PLAN.md. docs/PROBLEM_STATEMENT.md is the source of truth.
1. Work on ONE phase only: the one named in the user's prompt.
2. Use Planning mode: produce an implementation plan and wait for approval before editing.
3. Before coding, list files you will create/modify. Never touch files marked "DO NOT change".
4. Run all tests (new + earlier phases). Paste real output; never claim a pass you didn't observe.
5. Evaluate the phase CHECKPOINT item by item. If ANY item fails: STOP, report FAIL, propose fixes.
   Never start the next phase on your own. Never weaken or delete a test to pass.
6. Product rules: no login/registration/profile/admin/dashboard UI; this is NOT a banking app.
7. Safety rules: nothing reaches an LLM unmasked; no regulatory claim without a verified citation;
   agents other than the Coordinator never write to the DB; no secrets in code; never invent
   regulation text — retrieve it from kb/.
8. Ask before: installing large packages, deleting files, network downloads.
9. OFFLINE LLM ONLY: never add or call any hosted/online LLM API. Only local Ollama / open-weights models.
