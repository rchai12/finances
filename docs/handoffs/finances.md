# Tasks app: what the finances project needs to know

Written Nov 14, 2026 from the tasks app's design (`tasking/docs/`). For the finances project's architect and owner. Nothing here needs a change in finances now.

## Summary

The tasks app is the Python package `docket` in the `tasking` project. It owns tasks, reminders and calendar sync for the household's Mac. Phase 0 is specified and nothing is built yet. It doesn't connect to finances, and finances doesn't connect to it.

## Decisions that touch finances

| Decision | What it means here |
| --- | --- |
| Port 8767 | The tasks app's API listens on 127.0.0.1:8767. Finances keeps 8765 and Conductor 8766 |
| Conventions reused (Nov 14) | The tasks app's `phase-architect` and `phase-implementer-verifier` skills are modeled on the finances project's (actors, checklist, the reference-build hook, given files in a `fail<NN>` clone), with the email service's later refinements. A lesson learned there that applies to every project is worth copying back into finances' skill |
| A shared Discord service (Nov 14) | A new project will own the one Discord bot and post cards for every app. Finances has no Discord today. If finances ever wants a push, for example a failed sync or a budget alert instead of `fin health` only, it would go through that service rather than a bot of its own |
| No cross-domain plans in Conductor | Conductor plans one domain per request. A request like "remind me when the electricity bill is due" needs two plans (a finance read, then a tasks write), or a later Conductor phase that plans across domains |

## Possible later links (not decided)

- **Bills as tasks.** `get_upcoming` already knows recurring bills and their dates. A later phase could turn an upcoming bill into a proposal in the tasks app, which you'd approve on its card. That would be a design decision for both projects, and finances' rule that the agent only proposes would still hold.
- **Shared runtime habits.** The tasks app runs as a launchd LaunchAgent like the email service, and uses the same Keychain-only secrets and loopback-only listener rules as finances.
