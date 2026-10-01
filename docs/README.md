# Docs

- [architecture.md](architecture.md): goals, stack, layering, privacy boundary, cloud path
- [roadmap.md](roadmap.md): all phases, with outlines for those not yet specified
- [statement-formats.md](statement-formats.md): layout of each bank's PDF statement (synthetic examples)
- [testing.md](testing.md): test layers, rules, critical modules
- [phases/](phases/): detailed specs, one per phase
- [progress.md](progress.md): log the coding agent appends to after each phase

## Workflow

1. Give the coding agent one phase at a time, with a prompt like:

   > Read AGENTS.md, docs/architecture.md, docs/testing.md, docs/progress.md, and docs/phases/phase-NN-*.md.
   > Implement only Phase N. Stop when its acceptance criteria pass, then update docs/progress.md.

2. Review the result (run the acceptance commands yourself; ask the architect to review the diff).
3. Commit.
4. The architect writes or adjusts the next phase spec based on what was actually built.
