# AGENTS.md

Guidance for AI coding agents (Claude Code, Antigravity, Codex and others) working in this repository.

This is the Home Assistant integration (`plastic_slinger`, Python) for the self-hosted Plastic Slinger 3D print farm
manager. It reads only the app's API (`/api/v1`, documented in the app repository's `docs/API.md`) on the LAN.
The app, its design docs and the one to-do list for the app, this integration and the dashboard card live in the app
repository, [Plastic-Slinger](https://github.com/TopHATTwaffle/Plastic-Slinger); the card is in
[Plastic-Slinger-HA-Card](https://github.com/TopHATTwaffle/Plastic-Slinger-HA-Card).

## Backlog and docs
- Open work for this integration is tracked in the app repository's `docs/BACKLOG.md`, not here. When you add, finish
  or drop work on this integration, update that file too (a PR in the app repository), as its `AGENTS.md` asks.
- Keep `README.md` true in the same PR as any change (attributes, actions, snapshot proxy, options, install steps).
- The sensor attributes must stay backward compatible with the card: add keys, never change or remove them.

## Releases
- Bump `version` in `custom_components/plastic_slinger/manifest.json` and tag the merge commit `vX.Y.Z`; HACS only
  offers an update for a new tag.

## Tests
`pip install pytest-homeassistant-custom-component`, then `pytest`. The tests run the integration in a real Home
Assistant against a mocked service. New behavior gets a test; run the suite before saying a change is done.

## Public repository
This repository is mirrored publicly on GitHub: never write personal names or emails, private hostnames or LAN
addresses, API keys, or real printer/job data into code, tests, docs or commit messages.
