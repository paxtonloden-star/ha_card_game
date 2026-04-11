"""API views for HA Card Game live player and host UI."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import segno
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .const import (
    DOMAIN,
    GAME_MODE_CARDS,
    GAME_MODE_JUDGE_PARTY,
    GAME_MODE_TRIVIA,
    WS_EVENT_ERROR,
)
from .coordinator import CardGameCoordinator


def _as_clean_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip()


async def async_register_api(hass: HomeAssistant, coordinator: CardGameCoordinator) -> None:
    """Register API views."""
    if not str(coordinator.base_url or "").strip():
        try:
            coordinator.base_url = str(get_url(hass)).strip().rstrip("/")
        except Exception:
            coordinator.base_url = ""

    hass.http.register_view(CardGameStateView(coordinator))
    hass.http.register_view(CardGameJoinView(coordinator))
    hass.http.register_view(CardGameSubmitView(coordinator))
    hass.http.register_view(CardGameBuzzView(coordinator))
    hass.http.register_view(CardGamePickWinnerView(coordinator))
    hass.http.register_view(CardGameJoinQrView(coordinator))
    hass.http.register_view(CardGameWebSocketView(coordinator))
    hass.http.register_view(CardGameHostBootstrapView(coordinator))
    hass.http.register_view(CardGameHostActionView(coordinator))
    hass.http.register_view(CardGameHostPresetExportView(coordinator))
    hass.http.register_view(CardGameHostDeckExportView(coordinator))


class BaseCardGameView(HomeAssistantView):
    requires_auth = False

    def __init__(self, coordinator: CardGameCoordinator) -> None:
        self.coordinator = coordinator

    def json_error(self, message: str, status: int = 400) -> web.Response:
        return self.json({"ok": False, "error": message}, status_code=status)

    def current_user(self, request: web.Request):
        return request.get("hass_user")

    def request_user_name(self, request: web.Request) -> str:
        user = self.current_user(request)
        if user is None:
            return ""
        return str(
            getattr(user, "display_name", None)
            or getattr(user, "name", None)
            or getattr(user, "id", "")
            or ""
        ).strip()


class BaseCardGameHostView(BaseCardGameView):
    requires_auth = True

    async def ensure_host_access(self, request: web.Request) -> web.Response | None:
        user = self.current_user(request)
        if self.coordinator.user_can_host(user):
            return None
        return self.json_error("Host access denied", status=403)


class CardGameStateView(BaseCardGameView):
    url = f"/api/{DOMAIN}/state"
    name = f"api:{DOMAIN}:state"

    async def get(self, request: web.Request) -> web.Response:
        token = request.query.get("token")
        return self.json({"ok": True, "state": self.coordinator.player_state(token)})


class CardGameJoinView(BaseCardGameView):
    url = f"/api/{DOMAIN}/join"
    name = f"api:{DOMAIN}:join"

    async def post(self, request: web.Request) -> web.Response:
        data = await request.json()
        join_code = str(data.get("join_code", "")).strip().upper()
        if join_code != self.coordinator.join_code:
            return self.json_error("Invalid join code", 403)

        player_name = str(data.get("player_name", "")).strip() or self.request_user_name(request)
        if not player_name:
            return self.json_error("Player name is required")

        try:
            joined = await self.coordinator.async_join_player(player_name)
        except ValueError as err:
            return self.json_error(str(err))

        return self.json({"ok": True, **joined})


class CardGameSubmitView(BaseCardGameView):
    url = f"/api/{DOMAIN}/submit"
    name = f"api:{DOMAIN}:submit"

    async def post(self, request: web.Request) -> web.Response:
        data = await request.json()
        token = str(data.get("session_token", ""))
        card_text = str(data.get("card_text", ""))
        try:
            await self.coordinator.async_submit_for_token(token, card_text)
        except ValueError as err:
            return self.json_error(str(err))
        return self.json({"ok": True})


class CardGameBuzzView(BaseCardGameView):
    url = f"/api/{DOMAIN}/buzz"
    name = f"api:{DOMAIN}:buzz"

    async def post(self, request: web.Request) -> web.Response:
        data = await request.json()
        token = str(data.get("session_token", ""))
        try:
            result = await self.coordinator.async_buzz_for_token(token)
        except ValueError as err:
            return self.json_error(str(err))
        return self.json({"ok": True, **result})


class CardGamePickWinnerView(BaseCardGameView):
    url = f"/api/{DOMAIN}/pick_winner"
    name = f"api:{DOMAIN}:pick_winner"

    async def post(self, request: web.Request) -> web.Response:
        data = await request.json()
        token = str(data.get("session_token", ""))
        submission_id = str(data.get("submission_id", ""))
        try:
            await self.coordinator.async_pick_submission_for_token(token, submission_id)
        except ValueError as err:
            return self.json_error(str(err))
        return self.json({"ok": True})


class CardGameJoinQrView(BaseCardGameView):
    url = f"/api/{DOMAIN}/join_qr.svg"
    name = f"api:{DOMAIN}:join_qr"

    async def get(self, request: web.Request) -> web.StreamResponse:
        qr = segno.make(self.coordinator.join_url)
        buffer = BytesIO()
        qr.save(buffer, kind="svg", scale=6, border=2)
        return web.Response(body=buffer.getvalue(), content_type="image/svg+xml")


class CardGameWebSocketView(BaseCardGameView):
    url = f"/api/{DOMAIN}/ws"
    name = f"api:{DOMAIN}:ws"

    async def get(self, request: web.Request) -> web.StreamResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        await self.coordinator.async_register_socket(ws)

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    if msg.data == "ping":
                        await ws.send_json({"event": "pong"})
                    else:
                        await ws.send_json({"event": WS_EVENT_ERROR, "error": "Unsupported websocket command"})
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            await self.coordinator.async_unregister_socket(ws)

        return ws


class CardGameHostBootstrapView(BaseCardGameHostView):
    url = f"/api/{DOMAIN}/host/bootstrap"
    name = f"api:{DOMAIN}:host_bootstrap"

    async def get(self, request: web.Request) -> web.Response:
        denied = await self.ensure_host_access(request)
        if denied is not None:
            return denied

        host_users = await self.coordinator.async_available_host_users()
        reveal_state = self.coordinator.engine.state.as_dict().get("reveal", {})
        return self.json({
            "ok": True,
            "state": self.coordinator.player_state(None),
            "host": {
                "can_manage": True,
                "allowed_host_user_ids": list(self.coordinator.allowed_host_user_ids),
                "available_host_users": host_users,
                "host_policy": "admins_if_empty" if not self.coordinator.allowed_host_user_ids else "selected_users_only",
                "available_actions": [
                    "start_game", "set_game_mode", "next_round", "reset_game", "set_deck", "reload_decks",
                    "remove_player", "set_round_timer", "clear_round_timer", "set_reveal_config",
                    "save_custom_theme_preset", "delete_custom_theme_preset", "import_theme_presets",
                    "export_theme_presets", "import_deck_packs", "export_deck_packs", "set_ai_settings",
                    "set_parental_controls", "set_allowed_host_users", "approve_ai_queue_item",
                    "reject_ai_queue_item", "generate_ai_deck", "extend_deck_with_ai", "prepare_trivia",
                    "start_trivia_round", "grade_trivia_round", "set_trivia_settings", "set_trivia_voice_config",
                    "assign_player_team", "create_remote_invite", "buzz_player", "set_scene_media_config",
                    "trigger_scene_media_event", "start_tournament", "end_tournament", "update_profile",
                    "reset_profile", "delete_profile", "update_tournament_settings", "clear_tournament_history",
                    "save_custom_trivia_pack", "delete_custom_trivia_pack", "import_trivia_pack",
                ],
                "game_modes": [
                    {"value": GAME_MODE_TRIVIA, "label": "Trivia"},
                    {"value": GAME_MODE_CARDS, "label": "Cards Against Us"},
                    {"value": GAME_MODE_JUDGE_PARTY, "label": "Kids Cards Against Us"},
                ],
                "reveal": {
                    "sound_options": list(reveal_state.get("sound_options", [])),
                    "flip_style_options": list(reveal_state.get("flip_style_options", [])),
                    "tick_sound_pack_options": list(reveal_state.get("tick_sound_pack_options", [])),
                    "theme_preset_options": list(reveal_state.get("theme_preset_options", [])),
                    "custom_theme_presets": list(reveal_state.get("custom_theme_presets", [])),
                    "import_modes": ["merge", "replace"],
                    "export_url": f"/api/{DOMAIN}/host/presets/export",
                },
                "decks": {
                    "import_modes": ["merge", "replace"],
                    "export_url": f"/api/{DOMAIN}/host/decks/export",
                },
                "ai": {"settings": self.coordinator.ai_generator.settings.as_dict()},
                "trivia": {
                    "categories": list(self.coordinator._available_offline_trivia_categories()),
                    "age_ranges": ["6_8", "9_12", "13_17", "18_plus"],
                    "teams": ["Solo", "Team A", "Team B"],
                    "buzzer_modes": [False, True],
                    "sources": ["ai", "offline_curated"],
                    "answer_seconds": int(getattr(self.coordinator, "trivia_answer_seconds", 15)),
                    "reveal_seconds": int(getattr(self.coordinator, "trivia_reveal_seconds", 5)),
                    "auto_cycle_enabled": bool(getattr(self.coordinator, "trivia_auto_cycle_enabled", True)),
                    "voice": dict(getattr(self.coordinator, "trivia_voice_config", {})),
                    "tts_providers": await self.coordinator.async_available_tts_providers() if hasattr(self.coordinator, "async_available_tts_providers") else [],
                    "speaker_targets": await self.coordinator.async_available_speakers() if hasattr(self.coordinator, "async_available_speakers") else [],
                },
                "scene_media": dict(self.coordinator.scene_media_config),
                "tournament": self.coordinator._tournament_state(),
                "custom_trivia_packs": self.coordinator._custom_trivia_pack_summaries(),
            },
        })


class CardGameHostActionView(BaseCardGameHostView):
    url = f"/api/{DOMAIN}/host/action"
    name = f"api:{DOMAIN}:host_action"

    async def post(self, request: web.Request) -> web.Response:
        denied = await self.ensure_host_access(request)
        if denied is not None:
            return denied

        data = await request.json()
        action = str(data.get("action", "")).strip()

        try:
            if action == "start_game":
                await self.coordinator.async_start_game(data.get("deck_name"), game_mode=str(data.get("game_mode", "cards")))
            elif action == "set_game_mode":
                game_mode = str(data.get("game_mode", "")).strip()
                if game_mode not in {GAME_MODE_CARDS, GAME_MODE_JUDGE_PARTY, GAME_MODE_TRIVIA}:
                    return self.json_error("Unsupported game mode")
                self.coordinator.game_mode = game_mode
                await self.coordinator.async_refresh_from_engine()
            elif action == "next_round":
                self.coordinator.engine.next_round()
                await self.coordinator.async_refresh_from_engine()
            elif action == "reset_game":
                await self.coordinator.async_reset_lobby()
            elif action == "set_deck":
                await self.coordinator.async_set_deck(str(data.get("deck_name", "")).strip())
            elif action == "reload_decks":
                await self.coordinator.async_reload_decks()
            elif action == "remove_player":
                await self.coordinator.async_remove_player(str(data.get("player_name", "")).strip())
            elif action == "set_round_timer":
                await self.coordinator.async_set_round_timer(int(data.get("seconds", 0)))
            elif action == "clear_round_timer":
                await self.coordinator.async_set_round_timer(0)
            elif action == "set_reveal_config":
                await self.coordinator.async_set_reveal_config(
                    duration_ms=int(data["duration_ms"]) if data.get("duration_ms") is not None else None,
                    sound=_as_clean_str(data.get("sound")),
                    auto_advance_enabled=bool(data.get("auto_advance_enabled")) if data.get("auto_advance_enabled") is not None else None,
                    auto_advance_seconds=int(data["auto_advance_seconds"]) if data.get("auto_advance_seconds") is not None else None,
                    submission_reveal_enabled=bool(data.get("submission_reveal_enabled")) if data.get("submission_reveal_enabled") is not None else None,
                    submission_reveal_step_ms=int(data["submission_reveal_step_ms"]) if data.get("submission_reveal_step_ms") is not None else None,
                    flip_style=_as_clean_str(data.get("flip_style")),
                    tick_sound_pack=_as_clean_str(data.get("tick_sound_pack")),
                    theme_preset=_as_clean_str(data.get("theme_preset")),
                )
            elif action == "save_custom_theme_preset":
                await self.coordinator.async_save_custom_theme_preset(str(data.get("name", "")).strip(), str(data.get("description", "")).strip())
            elif action == "delete_custom_theme_preset":
                await self.coordinator.async_delete_custom_theme_preset(str(data.get("preset_slug", "")).strip())
            elif action == "import_theme_presets":
                payload = data.get("payload")
                if not isinstance(payload, dict):
                    return self.json_error("Import payload must be a JSON object")
                await self.coordinator.async_import_theme_presets(payload, mode=str(data.get("import_mode", "merge")).strip() or "merge")
            elif action == "import_deck_packs":
                payload = data.get("payload")
                if not isinstance(payload, dict):
                    return self.json_error("Import payload must be a JSON object")
                await self.coordinator.async_import_decks(payload, mode=str(data.get("import_mode", "merge")).strip() or "merge")
            elif action == "set_ai_settings":
                await self.coordinator.async_set_ai_settings(
                    enabled=bool(data.get("enabled")) if data.get("enabled") is not None else None,
                    endpoint=_as_clean_str(data.get("endpoint")),
                    model=_as_clean_str(data.get("model")),
                    api_key=_as_clean_str(data.get("api_key")),
                    use_local_fallback=bool(data.get("use_local_fallback")) if data.get("use_local_fallback") is not None else None,
                )
            elif action == "set_allowed_host_users":
                user_ids = data.get("user_ids")
                if not isinstance(user_ids, list):
                    return self.json_error("user_ids must be a list")
                await self.coordinator.async_set_allowed_host_users(user_ids)
            elif action == "set_parental_controls":
                categories = data.get("allowed_trivia_categories")
                await self.coordinator.async_set_parental_controls(
                    enabled=bool(data.get("enabled")) if data.get("enabled") is not None else None,
                    content_mode=_as_clean_str(data.get("content_mode")),
                    require_ai_approval=bool(data.get("require_ai_approval")) if data.get("require_ai_approval") is not None else None,
                    allow_remote_players=bool(data.get("allow_remote_players")) if data.get("allow_remote_players") is not None else None,
                    allowed_trivia_categories=list(categories) if isinstance(categories, list) else None,
                )
            elif action == "approve_ai_queue_item":
                result = await self.coordinator.async_approve_ai_queue_item(str(data.get("item_id", "")).strip())
                return self.json({"ok": True, "state": self.coordinator.player_state(None), "result": result})
            elif action == "reject_ai_queue_item":
                await self.coordinator.async_reject_ai_queue_item(str(data.get("item_id", "")).strip())
            elif action == "generate_ai_deck":
                deck_info = await self.coordinator.async_generate_ai_deck(
                    theme=str(data.get("theme", "Custom AI Pack")).strip(),
                    prompt_count=int(data.get("prompt_count", 12)),
                    white_count=int(data.get("white_count", 40)),
                    age_range=str(data.get("age_range", "18_plus")).strip(),
                    family_friendly=bool(data.get("family_friendly", True)),
                    style=str(data.get("style", "general_party")).strip() or "general_party",
                )
                return self.json({"ok": True, "state": self.coordinator.player_state(None), "deck": deck_info})
            elif action == "extend_deck_with_ai":
                deck_info = await self.coordinator.async_generate_ai_deck(
                    theme=str(data.get("theme", "Deck Expansion")).strip(),
                    prompt_count=int(data.get("prompt_count", 6)),
                    white_count=int(data.get("white_count", 20)),
                    age_range=str(data.get("age_range", "18_plus")).strip(),
                    family_friendly=bool(data.get("family_friendly", True)),
                    merge_into_slug=str(data.get("deck_name", "")).strip() or None,
                    style=str(data.get("style", "judge_party")).strip() or "judge_party",
                )
                return self.json({"ok": True, "state": self.coordinator.player_state(None), "deck": deck_info})
            elif action == "prepare_trivia":
                categories = data.get("categories")
                await self.coordinator.async_prepare_trivia(
                    category=str(data.get("category", "fun_facts")).strip(),
                    categories=[str(item).strip() for item in categories if str(item).strip()] if isinstance(categories, list) else None,
                    age_range=str(data.get("age_range", "18_plus")).strip(),
                    difficulty=_as_clean_str(data.get("difficulty")),
                    question_count=int(data.get("question_count", 10)),
                    source=str(data.get("source", "ai")).strip() or "ai",
                )
            elif action == "start_trivia_round":
                await self.coordinator.async_start_trivia_round()
            elif action == "grade_trivia_round":
                result = await self.coordinator.async_grade_trivia_round()
                return self.json({"ok": True, "state": self.coordinator.player_state(None), "result": result})
            elif action == "set_trivia_settings":
                await self.coordinator.async_set_trivia_settings(
                    team_mode=bool(data.get("team_mode")) if data.get("team_mode") is not None else None,
                    buzzer_mode=bool(data.get("buzzer_mode")) if data.get("buzzer_mode") is not None else None,
                    buzz_bonus=int(data.get("buzz_bonus")) if data.get("buzz_bonus") is not None else None,
                    steal_enabled=bool(data.get("steal_enabled")) if data.get("steal_enabled") is not None else None,
                    answer_seconds=int(data.get("answer_seconds")) if data.get("answer_seconds") is not None else None,
                    reveal_seconds=int(data.get("reveal_seconds")) if data.get("reveal_seconds") is not None else None,
                    auto_cycle_enabled=bool(data.get("auto_cycle_enabled")) if data.get("auto_cycle_enabled") is not None else None,
                )
            elif action == "set_trivia_voice_config":
                if not hasattr(self.coordinator, "async_set_trivia_voice_config"):
                    return self.json_error("Trivia voice config is not supported by this coordinator")
                speaker_targets = data.get("speaker_targets")
                await self.coordinator.async_set_trivia_voice_config(
                    enabled=bool(data.get("enabled")) if data.get("enabled") is not None else None,
                    provider_entity=_as_clean_str(data.get("provider_entity")),
                    speaker_targets=list(speaker_targets) if isinstance(speaker_targets, list) else None,
                    voice=_as_clean_str(data.get("voice")),
                    language=_as_clean_str(data.get("language")),
                    announce_answers=bool(data.get("announce_answers")) if data.get("announce_answers") is not None else None,
                    announce_correct_players=bool(data.get("announce_correct_players")) if data.get("announce_correct_players") is not None else None,
                    start_timer_after_voice=bool(data.get("start_timer_after_voice")) if data.get("start_timer_after_voice") is not None else None,
                    speech_rate_wpm=int(data.get("speech_rate_wpm")) if data.get("speech_rate_wpm") is not None else None,
                )
            elif action == "assign_player_team":
                await self.coordinator.async_assign_player_team(str(data.get("player_name", "")).strip(), str(data.get("team_name", "")).strip())
            elif action == "create_remote_invite":
                invite = await self.coordinator.async_create_remote_invite(str(data.get("player_name", "")).strip())
                return self.json({"ok": True, "state": self.coordinator.player_state(None), "invite": invite})
            elif action == "set_scene_media_config":
                await self.coordinator.async_set_scene_media_config(
                    enabled=bool(data.get("enabled")) if data.get("enabled") is not None else None,
                    start_scene=_as_clean_str(data.get("start_scene")),
                    reveal_scene=_as_clean_str(data.get("reveal_scene")),
                    winner_scene=_as_clean_str(data.get("winner_scene")),
                    media_player=_as_clean_str(data.get("media_player")),
                    start_sound=_as_clean_str(data.get("start_sound")),
                    reveal_sound_media=_as_clean_str(data.get("reveal_sound_media")),
                    winner_sound=_as_clean_str(data.get("winner_sound")),
                    volume_level=float(data.get("volume_level")) if data.get("volume_level") is not None else None,
                )
            elif action == "trigger_scene_media_event":
                await self.coordinator.async_trigger_scene_media_event(str(data.get("event_name", "winner")).strip() or "winner", _as_clean_str(data.get("winner")))
            elif action == "start_tournament":
                await self.coordinator.async_start_tournament(
                    name=str(data.get("name", "House Tournament")).strip() or "House Tournament",
                    target_score=int(data.get("target_score", 10)),
                    reset_scores=bool(data.get("reset_scores", True)),
                )
            elif action == "end_tournament":
                await self.coordinator.async_end_tournament()
            elif action == "update_profile":
                result = await self.coordinator.async_update_profile(str(data.get("player_name", "")).strip(), dict(data.get("updates", {})))
                return self.json({"ok": True, "state": self.coordinator.player_state(None), "result": result})
            elif action == "reset_profile":
                await self.coordinator.async_reset_profile(str(data.get("player_name", "")).strip())
            elif action == "delete_profile":
                await self.coordinator.async_delete_profile(str(data.get("player_name", "")).strip())
            elif action == "update_tournament_settings":
                await self.coordinator.async_update_tournament_settings(
                    name=_as_clean_str(data.get("name")),
                    target_score=int(data.get("target_score")) if data.get("target_score") is not None else None,
                    enabled=bool(data.get("enabled")) if data.get("enabled") is not None else None,
                )
            elif action == "clear_tournament_history":
                await self.coordinator.async_clear_tournament_history()
            elif action == "import_trivia_pack":
                questions = data.get("questions")
                if not isinstance(questions, list):
                    return self.json_error("questions must be a list")
                result = await self.coordinator.async_save_custom_trivia_pack(
                    slug=str(data.get("slug", "")).strip(),
                    name=str(data.get("name", "")).strip(),
                    description=str(data.get("description", "")).strip(),
                    questions=questions,
                )
                return self.json({"ok": True, "state": self.coordinator.player_state(None), "result": result})
            elif action == "save_custom_trivia_pack":
                result = await self.coordinator.async_save_custom_trivia_pack(
                    slug=str(data.get("slug", "")).strip(),
                    name=str(data.get("name", "")).strip(),
                    description=str(data.get("description", "")).strip(),
                    questions=list(data.get("questions", [])),
                )
                return self.json({"ok": True, "state": self.coordinator.player_state(None), "result": result})
            elif action == "delete_custom_trivia_pack":
                await self.coordinator.async_delete_custom_trivia_pack(str(data.get("slug", "")).strip())
            else:
                return self.json_error("Unknown host action", 404)
        except ValueError as err:
            return self.json_error(str(err))

        return self.json({"ok": True, "state": self.coordinator.player_state(None)})


class CardGameHostPresetExportView(BaseCardGameHostView):
    url = f"/api/{DOMAIN}/host/presets/export"
    name = f"api:{DOMAIN}:host_preset_export"

    async def get(self, request: web.Request) -> web.Response:
        include_builtin = str(request.query.get("include_builtin", "false")).lower() in {"1", "true", "yes", "on"}
        payload = await self.coordinator.async_export_theme_presets(include_builtin=include_builtin)
        return web.json_response(payload, headers={"Content-Disposition": 'attachment; filename="ha_card_game_theme_presets.json"'})


class CardGameHostDeckExportView(BaseCardGameHostView):
    url = f"/api/{DOMAIN}/host/decks/export"
    name = f"api:{DOMAIN}:host_deck_export"

    async def get(self, request: web.Request) -> web.Response:
        include_builtin = str(request.query.get("include_builtin", "false")).lower() in {"1", "true", "yes", "on"}
        payload = await self.coordinator.async_export_decks(include_builtin=include_builtin)
        return web.json_response(payload, headers={"Content-Disposition": 'attachment; filename="ha_card_game_deck_packs.json"'})
