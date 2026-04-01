"""Assist intent handlers for HA Card Game."""

from __future__ import annotations

from homeassistant.helpers import intent

from .const import DOMAIN
from .coordinator import CardGameCoordinator




async def async_setup_intents(hass) -> None:
    """Register Assist intents when Home Assistant loads the intent platform."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinator = None
    if isinstance(domain_data, dict):
        coordinator = next(iter(domain_data.values()), None)
    if coordinator is None:
        return
    await async_register_intents(hass, coordinator)

async def async_register_intents(hass, coordinator: CardGameCoordinator) -> None:
    intent.async_register(hass, JoinGameIntentHandler(coordinator))
    intent.async_register(hass, SubmitCardIntentHandler(coordinator))
    intent.async_register(hass, PickWinnerIntentHandler(coordinator))
    intent.async_register(hass, NextRoundIntentHandler(coordinator))
    intent.async_register(hass, StartGameIntentHandler(coordinator))


class _BaseHandler(intent.IntentHandler):
    def __init__(self, coordinator: CardGameCoordinator) -> None:
        self.coordinator = coordinator

    def _response(self, intent_obj: intent.Intent, speech: str) -> intent.IntentResponse:
        response = intent_obj.create_response()
        response.async_set_speech(speech)
        return response

    def _slot(self, slots, key: str) -> str | None:
        value = slots.get(key)
        if not value:
            return None
        if hasattr(value, 'value'):
            return str(value.value).strip()
        return str(value).strip()


class JoinGameIntentHandler(_BaseHandler):
    intent_type = 'HACardGameJoin'
    slot_schema = {'player_name': str}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        player_name = self._slot(intent_obj.slots, 'player_name')
        if not player_name:
            return self._response(intent_obj, 'I need a player name to join the game.')
        joined = await self.coordinator.async_join_player(player_name)
        return self._response(intent_obj, f"{joined['player_name']} joined the card game.")


class SubmitCardIntentHandler(_BaseHandler):
    intent_type = 'HACardGameSubmit'
    slot_schema = {'player_name': str, 'card_text': str, 'hand_index': int}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        player_name = self._slot(intent_obj.slots, 'player_name')
        if not player_name:
            return self._response(intent_obj, 'Say the player name when submitting a card.')
        player = self.coordinator._find_player(player_name)
        if player is None:
            return self._response(intent_obj, f"I could not find player {player_name}.")
        card_text = self._slot(intent_obj.slots, 'card_text')
        hand_index = self._slot(intent_obj.slots, 'hand_index')
        if not card_text and hand_index:
            try:
                card_text = player.hand[int(hand_index)-1]
            except Exception:
                return self._response(intent_obj, 'That hand card number is not available.')
        if not card_text:
            return self._response(intent_obj, 'Say the card text, or the hand card number, when submitting.')
        self.coordinator.engine.submit_card(player.name, card_text)
        await self.coordinator.async_refresh_from_engine()
        return self._response(intent_obj, f"Submitted {player.name}'s card.")


class PickWinnerIntentHandler(_BaseHandler):
    intent_type = 'HACardGamePickWinner'
    slot_schema = {'submission_number': int}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        number = self._slot(intent_obj.slots, 'submission_number')
        if not number:
            return self._response(intent_obj, 'Say which anonymous submission won, like submission 2.')
        self.coordinator.engine.pick_winner_submission(f'sub_{int(number)}')
        await self.coordinator.async_refresh_from_engine()
        winner = self.coordinator.engine.state.winner or 'The winner'
        return self._response(intent_obj, f'{winner} won the round.')


class NextRoundIntentHandler(_BaseHandler):
    intent_type = 'HACardGameNextRound'
    slot_schema = {}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        self.coordinator.engine.next_round()
        await self.coordinator.async_refresh_from_engine()
        judge = self.coordinator.engine.state.current_judge or 'Nobody'
        return self._response(intent_obj, f'Next round started. {judge} is the judge.')


class StartGameIntentHandler(_BaseHandler):
    intent_type = 'HACardGameStart'
    slot_schema = {'deck_name': str}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        deck_name = self._slot(intent_obj.slots, 'deck_name') or self.coordinator.engine.state.deck_name
        await self.coordinator.async_start_game(deck_name)
        prompt = self.coordinator.engine.state.current_prompt or 'The round is ready.'
        return self._response(intent_obj, f'Card game started. Prompt: {prompt}')
