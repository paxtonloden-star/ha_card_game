# Modular frontend scaffold

This directory is the safer replacement path for the legacy single-file frontend.

## Goals
- Keep `frontend/index.html` working while migrating incrementally.
- Split UI concerns into focused modules.
- Make mode-specific UIs easier to maintain.
- Reduce the risk of breaking host, player, and TV views when changing one area.

## Proposed rollout
1. Keep the current `index.html` live.
2. Move shared helpers and network code into `app/` modules.
3. Rebuild host, player, and TV sections as composable render functions.
4. Swap the live `index.html` to the new module bootstrap once parity is good enough.

## Files
- `app/bootstrap.js` bootstraps the modular app shell.
- `app/api.js` centralizes all backend calls.
- `app/state.js` stores runtime state and derives helpers like `isTriviaMode`.
- `app/utils.js` shared DOM and formatting helpers.
- `app/components/host.js` host controls, mode selector, and collapsible sections.
- `app/components/player.js` join and submission UX.
- `app/components/tv.js` TV display rendering.

## Notes
This scaffold is intentionally lightweight and non-destructive. It gives the repo a maintainable frontend direction without replacing the current production page in one risky step.
