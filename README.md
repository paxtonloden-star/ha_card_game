# HA Card Game Starter

A Home Assistant custom integration starter for a judge-based party card game.

## Included in this version

- custom integration scaffold
- persistent in-memory game engine
- live browser UI for host and players
- QR join flow for phones on the same network
- websocket push for live room updates
- deck pack manager with built-in and file-based JSON decks
- Assist intent handlers and starter custom sentences
- HACS metadata and example package YAML

## New in 0.3.0

- removed 2-second polling from the player UI in favor of a websocket feed
- added white-card hands with refill per round
- added deck loading from `/config/ha_card_game_decks/*.json`
- added built-in `default_family` and `smart_home_chaos` decks
- added Assist intents for join, start, submit, pick winner, and next round

## Live UI flow

1. Install the custom component.
2. Open the **Card Game** sidebar panel.
3. Players scan the QR code or open the join URL.
4. Once at least 3 players have joined, call `ha_card_game.start_game`.
5. Players submit answers from their phones using a hand of white cards.
6. The current judge picks the winner from their phone.
7. Call `ha_card_game.next_round` or say “next card game round” to continue.

## Deck pack format

Save JSON files in:

- `/config/ha_card_game_decks/*.json`

Example:

```json
{
  "slug": "office_chaos",
  "name": "Office Chaos",
  "description": "Work-safe office deck",
  "allow_free_text": false,
  "hand_size": 7,
  "prompts": ["Quarterly planning was ruined by ____."],
  "white_cards": ["reply-all", "a broken spreadsheet", "free pizza"]
}
```

Then call `ha_card_game.reload_decks`.

## Assist examples

- “join the card game as Brian”
- “start the card game with smart home chaos”
- “submit card 2 for Brian”
- “submission 3 wins”
- “next card game round”

## Important notes

- The public player endpoints are still designed for trusted home/LAN use.
- The websocket feed is intentionally simple and broadcasts room state changes.
- Built-in decks are family-safe starters so you can wire up mechanics first.
