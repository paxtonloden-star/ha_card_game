# HA Card Game

HA Card Game is a custom Home Assistant integration that turns Home Assistant into a party-game host for two game styles:

- **Judge-based card play** inspired by fill-in-the-blank party card games
- **Multiplayer trivia** with phone-based answers, team mode, buzzer mode, and steal-chance rounds

It is built to feel like a living-room game system inside Home Assistant: the host runs the game from the HA sidebar, players join from their phones with a QR code or link, and a TV or wall tablet can show a full-screen host display for prompts, reveals, scores, and trivia results.

## What this project includes

### Card game features
- live player and host browser UI
- QR join flow and join codes
- white-card hands with refill each round
- anonymous judge view and winner selection
- TV mode with reveal sequences and winner overlays
- configurable reveal sounds, flip styles, tick sound packs, and theme presets
- custom preset manager with import/export
- deck pack manager with import/export
- AI-generated deck packs
- AI expansion of existing decks
- AI moderation queue with approve/reject flow
- parental content controls for AI, trivia, and remote access

### Trivia features
- trivia mode with multiple-choice answers on phones
- categories including:
  - history
  - fun facts
  - geography
  - movies
  - 1990s
  - 2000s
  - 2010s
  - computer games
- age-range tuning and AI-generated trivia questions
- multiplayer grading and TV reveal flow
- team-vs-team mode
- fastest-answer buzzer mode
- wrong-answer steal chance

### Home Assistant integration features
- config flow for setup
- sidebar panel
- sensors and buttons
- Home Assistant services for game control
- Assist intent scaffolding and starter custom sentences
- websocket push for live room updates
- HACS-friendly repo layout

## Current status

This repo is a **starter implementation and MVP**. It already has a lot of working gameplay scaffolding, but you should still treat it like an actively evolving custom integration rather than a polished App Store-style package.

Especially important:
- the game is best suited for **trusted home use**
- remote play should be done through **secure Home Assistant remote access**, not by exposing raw endpoints directly to the internet
- AI generation includes a **local fallback generator** so demos and tests still work without a live API key

## Repository layout

```text
custom_components/ha_card_game/
  __init__.py
  manifest.json
  config_flow.py
  coordinator.py
  game_engine.py
  deck_manager.py
  trivia_manager.py
  ai_generator.py
  api.py
  panel.py
  sensor.py
  button.py
  intent.py
  frontend/
docs/
examples/
tests/
```

## Requirements

- Home Assistant with support for custom integrations
- A modern browser for host/player/TV screens
- Optional: a secure remote-access method such as Home Assistant Cloud, VPN, or Tailscale for remote players
- Optional: an OpenAI-compatible API endpoint if you want live AI generation instead of the built-in local fallback

## Install

### Option 1: HACS-style install

1. Copy this repo into a Git repository you control.
2. Add that repository to HACS as a custom repository.
3. Install **HA Card Game** from HACS.
4. Restart Home Assistant.

### Option 2: Manual install

1. Copy the folder below into your Home Assistant config directory:

   ```text
   custom_components/ha_card_game
   ```

2. Your Home Assistant config should end up looking like:

   ```text
   /config/custom_components/ha_card_game/
   ```

3. Restart Home Assistant.

## Initial setup

1. In Home Assistant, go to **Settings → Devices & Services**.
2. Click **Add Integration**.
3. Search for **HA Card Game**.
4. Complete the config flow.
5. Open the new **Card Game** item in the Home Assistant sidebar.

## Basic setup flow

### For card game mode
1. Open the sidebar panel.
2. Use the host/admin controls to confirm the active deck.
3. Let players join by QR code, join link, or invite link.
4. Start the game.
5. Players submit cards from their phones.
6. The judge picks a winner.
7. Advance to the next round.

### For trivia mode
1. Open the sidebar panel.
2. Switch or prepare the session for trivia.
3. Choose category, age range, and question count.
4. Optionally enable team mode, buzzer mode, and steal chance.
5. Start trivia.
6. Players answer from their phones.
7. The TV screen reveals correct answers, team standings, and round outcomes.

## Deck setup

Deck JSON files can be stored in:

```text
/config/ha_card_game_decks/*.json
```

Example deck:

```json
{
  "slug": "office_chaos",
  "name": "Office Chaos",
  "description": "Work-safe office deck",
  "allow_free_text": false,
  "hand_size": 7,
  "prompts": [
    "Quarterly planning was ruined by ____."
  ],
  "white_cards": [
    "reply-all",
    "a broken spreadsheet",
    "free pizza"
  ]
}
```

After adding or changing deck files, reload decks from the host panel or call the reload service.

## AI generation

The integration includes two AI generation paths:

- **remote AI generation** through an OpenAI-compatible endpoint
- **local fallback generation** for offline demos, tests, or when no API key is configured

AI generation can be used for:
- creating brand-new deck packs
- adding new AI-created cards into an existing deck
- generating trivia questions by category, age range, and difficulty profile

When parental controls are enabled, AI output can be filtered and routed into a host approval queue before it becomes playable.

### Recommended AI setup

If you want live AI-backed content, configure:
- API key
- endpoint URL
- model name

If you do not configure those, the integration can still generate starter-style local content.

## Parental controls and AI moderation

The host panel includes a parental-controls section for:
- enabling or disabling parental safeguards
- choosing a content mode: `family_safe`, `teen`, or `adult`
- requiring AI approval before new packs or trivia are used
- allowing or blocking remote players
- limiting which trivia categories are allowed

When **AI approval** is enabled:
1. AI-generated decks and trivia go into a moderation queue.
2. The host reviews each queued item.
3. The host approves or rejects it from the sidebar panel.

Family-safe mode also applies a lightweight blocked-term filter to generated prompts, white cards, and trivia text before the review step.

## Remote player setup

For remote players, use one of these approaches:

- Home Assistant Cloud remote URL
- VPN access to your home network
- Tailscale or similar private networking

Recommended approach:
1. Make sure your Home Assistant instance already has secure remote access.
2. Open the host panel.
3. Generate or copy the player invite link.
4. Send the invite link to the remote player.

Do **not** expose custom endpoints directly to the internet without a secure access layer.

## TV mode

TV mode is designed for a large display in the room.

It can show:
- prompt text
- join code and QR code
- live scoreboard
- player list
- trivia question and choices
- buzzer owner
- reveal animations
- winner and answer overlays

TV mode works best on:
- a wall tablet
- a browser on a smart TV
- a mini PC or streaming box browser

## Theme presets and custom presets

Built-in theme presets bundle reveal settings together, including:
- reveal sound
- flip style
- tick sound pack
- auto-advance behavior
- submission reveal timing
- TV theme visuals

Custom presets can be:
- saved from the current host settings
- updated
- deleted
- exported
- imported into another Home Assistant instance

## Deck pack import/export

Deck packs can also be exported and imported so you can move custom game content between Home Assistant instances.

## Services

The integration exposes service actions including:
- `ha_card_game.start_game`
- `ha_card_game.add_player`
- `ha_card_game.submit_card`
- `ha_card_game.pick_winner`
- `ha_card_game.next_round`
- `ha_card_game.reset_game`
- `ha_card_game.set_deck`
- `ha_card_game.reload_decks`

See `custom_components/ha_card_game/services.yaml` for field details.

## Assist examples

Example phrases included in the starter scaffolding:
- “join the card game as Brian”
- “start the card game with smart home chaos”
- “submit card 2 for Brian”
- “submission 3 wins”
- “next card game round”

## Example package

There is an example helper/package file here:

```text
examples/package.yaml
```

Use it as a starting point if you want extra dashboard helpers or package-based organization.

## Development notes

- `segno` is used for QR generation
- websocket updates are used for live room state changes
- tests are included for engine, deck manager, AI/trivia flow, and buzzer/steal logic

## Suggested next features

Good next additions from here would be:

1. **Parental content controls**
   - deck-level family filters
   - per-room safe mode
   - allow/block categories by player age

2. **Player profiles and progression**
   - persistent stats by player
   - streaks, badges, funniest-answer awards
   - seasonal leaderboards

3. **Scheduled game nights**
   - create a Home Assistant calendar event
   - auto-open TV mode scene
   - reminders and countdown announcements

4. **Media and device integration**
   - winner lights/scenes
   - sound effects through media players
   - button or NFC tap-to-buzz support

5. **Question review and moderation**
   - approve AI-generated cards before they enter a live deck
   - ban or retire weak cards
   - favorite and replay top submissions

6. **Trivia content packs**
   - curated offline packs by grade band
   - holiday packs
   - local/family history packs
   - household custom knowledge packs

7. **Tournament mode**
   - bracket play
   - team seasons
   - cumulative party-night ranking

8. **Companion automations**
   - award chore points to winners
   - unlock bonus rewards
   - turn game outcomes into Home Assistant achievements or badges

## Troubleshooting

### Sidebar panel does not appear
- restart Home Assistant after copying the integration
- confirm the integration loaded successfully
- confirm panel support is enabled in the integration setup

### Players cannot join
- verify the player device can reach your Home Assistant URL
- check whether you are using a local-only URL while the player is remote
- confirm your secure remote access path is working first

### AI generation is not using live AI
- verify the API key, endpoint, and model settings
- if those are not configured, local fallback generation may still make it look like generation is working

### Deck changes are not showing
- reload decks from the host controls or call `ha_card_game.reload_decks`
- verify the JSON file is valid and stored under `/config/ha_card_game_decks/`

## Disclaimer

This project is intended for private/home use and custom Home Assistant setups. Review the content of decks and AI-generated material before using it with children or mixed-age groups.


## Newly added advanced features

### Persistent player profiles
- Tracks per-player card round wins, trivia accuracy, buzzes, steal wins, total points, and tournament wins.
- Profiles persist in Home Assistant storage across restarts.

### Scene and media integration
- Optional host-controlled scene/media automation hooks for game start, reveal, and winner events.
- Supports scene entities plus media-player sound cues for winner moments and room ambiance.

### Tournament mode
- Start a named tournament with a target score.
- Keeps a rolling history of rounds and automatically crowns a champion when the target score is reached.
- Can be used for cards mode or trivia mode.

### Offline curated trivia packs
- Built-in offline trivia question packs for:
  - history
  - fun facts
  - geography
  - movies
  - 1990s
  - 2000s
  - 2010s
  - computer games
- Works without an AI API key.
- Still supports age-range and difficulty tuning.

### Host actions added
- `set_scene_media_config`
- `trigger_scene_media_event`
- `start_tournament`
- `end_tournament`
- `prepare_trivia` now supports `source: offline_curated`


## Manual host editor

The host panel now includes a **Manual host editor** for operational cleanup and production-minded administration:
- edit or reset persistent player profile stats
- update tournament name, target score, and enabled state
- clear tournament history without wiping the whole lobby
- create, edit, and delete **custom offline trivia packs** from the UI using JSON questions

Example question JSON:

```json
[
  {
    "question": "Which planet is known as the Red Planet?",
    "correct_answer": "Mars",
    "choices": ["Venus", "Mars", "Jupiter", "Mercury"],
    "accepted_answers": ["Mars"],
    "difficulty": "easy",
    "age_range": "9_12",
    "explanation": "Mars is often called the Red Planet because of iron oxide on its surface."
  }
]
```

## Production hardening roadmap

This repo is now closer to a production-style Home Assistant custom integration, but I still recommend the following before calling it production-ready:
- move more host settings into a true **options flow**
- add **diagnostics** output for support bundles
- add **repair issues** for invalid AI/remote/trivia configuration
- use config-entry **runtime data** consistently for live coordinator/runtime objects
- add broader automated tests for config flow, API auth edges, and storage migrations
- place remote access behind secure Home Assistant remote access or a VPN instead of exposing raw public endpoints

These recommendations align with Home Assistant's current integration quality guidance around options flows, diagnostics, repair flows, and runtime data.


## Production-ready configuration upgrades

This build now includes a more complete Home Assistant integration surface:

- multi-step **Options Flow** with selector-based inputs
- support for storing an **AI API key** in integration options
- optional **remote base URL override** for invite links
- richer **Diagnostics** output with redacted runtime state
- **Repair Issues** for missing remote URL, invalid AI setup, and empty trivia category selections
- **System Health** reporting for decks, players, websocket clients, and AI state

### Options Flow

Open the integration in Home Assistant and choose **Configure**. The flow now has separate sections for:

- General
- Content and safety
- Remote access
- AI
- Trivia

### Diagnostics

Diagnostics now include:

- sanitized entry data and options
- runtime state summary
- scene/media summary
- tournament summary
- storage snapshot metadata

Secrets such as API keys, tokens, join codes, and remote invite payloads are redacted.

### Repairs

The integration can now raise repair issues when:

- remote players are enabled without a usable external URL
- AI generation is enabled without an API key and without fallback
- no trivia categories are enabled

### System Health

System health exposes high-level operational signals such as:

- whether the integration is loaded
- number of players
- deck counts
- custom trivia pack counts
- websocket client count
- AI enabled state


## Data migrations and compatibility

This integration now includes a storage migration layer for saved game state, AI moderation data, player profiles, custom trivia packs, remote invites, and reveal/theme settings. Older payload shapes are normalized on load and then re-saved in the current schema automatically.

Compatibility handling currently covers legacy keys such as old theme fields, profile lists, trivia pack lists, parental control field names, remote invite lists, and earlier AI setting names. Diagnostics and system health now expose the active storage schema version and migration history to make upgrades easier to troubleshoot.
