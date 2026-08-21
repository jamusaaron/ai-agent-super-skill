# Jamie's AI Cabinet

Established 2026-08-21. This directory is the Cabinet's shared workspace: every
role reads from and writes to these registers, and nothing that matters happens
outside them.

## Contents

| File | Purpose |
|------|---------|
| `ROLE_REGISTER.md` | The twelve proposed roles, their mandates, active status, and the Case Room handoff |
| `TASK_REGISTER.md` | Every task the Cabinet takes on, from intake to outcome |
| `DECISION_LOG.md` | Jamie's decisions and approvals, recorded verbatim with scope and date |
| `SOURCE_REGISTER.csv` | Every source and system the Cabinet may draw on, and its connection status |
| `ROUTINE_REGISTER.md` | Recurring routines, their owners, cadence, and status |

## Standing Orders (approval rules)

These bind every role, active or dormant, with no exceptions:

1. **Restricted actions.** No bot may **send**, **publish**, **submit**,
   **delete**, **overwrite**, **purchase**, **change permissions**, or
   **access a departmental system** without Jamie's explicit approval.
2. **Draft-only by default.** All work stops at "ready for Jamie". The Cabinet
   prepares; Jamie pulls the trigger.
3. **Approval is per instance.** Approval covers one named action, once.
   It does not carry over to similar or repeated actions.
4. **Silence is refusal.** If Jamie has not explicitly approved, the answer
   is no.
5. **Approvals are logged.** Every approval (and refusal worth remembering)
   is recorded in `DECISION_LOG.md` with its exact scope and date.
6. **No external accounts** are connected until Jamie instructs otherwise.
   `SOURCE_REGISTER.csv` is the single record of what is and is not connected.

## Current limitations

- The Cabinet is a governance structure, not yet a fleet: the twelve roles are
  register entries and operating rules, not independently running bots. Work is
  performed by the assisting agent acting *as* the assigned role, following the
  handoff order.
- Enforcement of the Standing Orders is procedural (documented and checked at
  the Sceptic and Chief stages), not technical. No system-level permission
  boundaries exist yet because no departmental systems are connected.
- No external accounts (mail, storage, calendar, or any departmental system)
  are connected, per instruction. Tasks requiring them will be marked
  **blocked: awaiting connection approval** in the task register.
- The shared workspace lives in this git repository, so its history is the
  audit trail. Anything not committed here does not count as Cabinet record.
