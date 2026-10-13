# Docs

- [architecture.md](architecture.md): goals, stack, layering, agent interface, privacy boundary
- [roadmap.md](roadmap.md): all phases, with outlines for those not yet specified
- [statement-formats.md](statement-formats.md): layout of each bank's PDF statement (synthetic examples)
- [testing.md](testing.md): test layers, rules, critical modules
- [phases/](phases/): detailed specs, one per phase
- `verification/`: one guide per phase, for the second agent that checks the implementation against the spec
- [progress.md](progress.md): log the coding agent appends to after each phase

## Workflow

1. Commit the spec and its verification guide, so `git status` is clean. Then give the coding agent one phase at a time, with a prompt like:

   > Read AGENTS.md, docs/architecture.md, docs/testing.md, docs/progress.md, and docs/phases/phase-NN-*.md.
   > Implement only Phase N. Stop when its acceptance criteria pass, then update docs/progress.md.

2. Give a second coding agent the matching guide in `verification/`, with a prompt like:

   > Read AGENTS.md, docs/phases/phase-NN-*.md, and docs/verification/phase-NN-*.md.
   > Follow the verification guide against the current diff. Do not modify files. Report the verdict.

   A FAIL goes back to the coding agent with the verifier's findings, in the form the guide's last section gives.
3. Commit.
4. The architect writes or adjusts the next phase spec and its verification guide based on what was actually built.

The architect's rules for sizing and writing specs and verification guides are in `.claude/skills/phase-architect/SKILL.md`. The stricter step-by-step format used for Phases 2a to 3a, when the coder was a small local model, is the user-level skill `local-coder-specs`; those specs remain here as its examples.
