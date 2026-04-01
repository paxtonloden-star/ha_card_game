"""Constants for HA Card Game."""

from __future__ import annotations

DOMAIN = "ha_card_game"
PLATFORMS = ["sensor", "button"]

DEFAULT_TITLE = "HA Card Game"
DEFAULT_DECK = "default_family"
DEFAULT_HAND_SIZE = 7

STORAGE_VERSION = 7
CURRENT_STORAGE_SCHEMA_VERSION = 8
STORAGE_KEY = f"{DOMAIN}_state"

SERVICE_START_GAME = "start_game"
SERVICE_ADD_PLAYER = "add_player"
SERVICE_SUBMIT_CARD = "submit_card"
SERVICE_PICK_WINNER = "pick_winner"
SERVICE_NEXT_ROUND = "next_round"
SERVICE_RESET_GAME = "reset_game"
SERVICE_SET_DECK = "set_deck"
SERVICE_RELOAD_DECKS = "reload_decks"

STATE_IDLE = "idle"
STATE_LOBBY = "lobby"
STATE_SUBMITTING = "submitting"
STATE_JUDGING = "judging"
STATE_RESULTS = "results"

CONF_ENABLE_PANEL = "enable_panel"
CONF_MAX_ROUNDS = "max_rounds"
CONF_ALLOW_REPEAT_PROMPTS = "allow_repeat_prompts"
CONF_CONTENT_MODE = "content_mode"
CONF_REQUIRE_AI_APPROVAL = "require_ai_approval"
CONF_ALLOW_REMOTE_PLAYERS = "allow_remote_players"
CONF_ALLOWED_TRIVIA_CATEGORIES = "allowed_trivia_categories"
CONF_DEFAULT_GAME_MODE = "default_game_mode"
CONF_DEFAULT_TRIVIA_SOURCE = "default_trivia_source"
CONF_AI_ENABLED = "ai_enabled"
CONF_AI_ENDPOINT = "ai_endpoint"
CONF_AI_MODEL = "ai_model"
CONF_AI_API_KEY = "ai_api_key"
CONF_AI_USE_LOCAL_FALLBACK = "ai_use_local_fallback"
CONF_REMOTE_BASE_URL = "remote_base_url"


DEFAULT_ENABLE_PANEL = True
DEFAULT_MAX_ROUNDS = 10
DEFAULT_ALLOW_REPEAT_PROMPTS = False
DEFAULT_CONTENT_MODE = "family_safe"
DEFAULT_REQUIRE_AI_APPROVAL = True
DEFAULT_ALLOW_REMOTE_PLAYERS = False
DEFAULT_DEFAULT_GAME_MODE = "cards"
DEFAULT_DEFAULT_TRIVIA_SOURCE = "offline_curated"
DEFAULT_AI_ENABLED = False
DEFAULT_AI_USE_LOCAL_FALLBACK = True
DEFAULT_REMOTE_BASE_URL = ""

JOIN_CODE_LENGTH = 6
PLAYER_TOKEN_LENGTH = 32
ADMIN_TOKEN_LENGTH = 32

DECKS_FOLDER_NAME = "ha_card_game_decks"
WS_EVENT_STATE = "state"
WS_EVENT_JOINED = "joined"
WS_EVENT_ERROR = "error"

DEFAULT_REVEAL_DURATION_MS = 6500
DEFAULT_REVEAL_SOUND = "victory_chime"
DEFAULT_AUTO_ADVANCE_ENABLED = False
DEFAULT_AUTO_ADVANCE_SECONDS = 8
DEFAULT_SUBMISSION_REVEAL_ENABLED = True
DEFAULT_SUBMISSION_REVEAL_STEP_MS = 1800
DEFAULT_FLIP_STYLE = "arcade_flip"
DEFAULT_TICK_SOUND_PACK = "arcade_ticks"
DEFAULT_THEME_PRESET = "arcade_night"

REVEAL_SOUNDS = [
    "off",
    "victory_chime",
    "confetti_hits",
    "arcade_stinger",
    "dramatic_rise",
]


FLIP_STYLES = [
    "arcade_flip",
    "dramatic_flip",
    "clean_flip",
    "party_bounce",
]

TICK_SOUND_PACKS = [
    "arcade_ticks",
    "dramatic_ticks",
    "clean_clicks",
    "party_pops",
]


THEME_PRESETS = [
    {
        "slug": "arcade_night",
        "name": "Arcade Night",
        "description": "Fast neon arcade pacing with confident flip cues and auto-advance enabled.",
        "reveal_sound": "arcade_stinger",
        "flip_style": "arcade_flip",
        "tick_sound_pack": "arcade_ticks",
        "auto_advance_enabled": True,
        "auto_advance_seconds": 7,
        "submission_reveal_enabled": True,
        "submission_reveal_step_ms": 1500,
        "reveal_duration_ms": 6200,
        "theme": {
            "slug": "arcade_night",
            "name": "Arcade Night",
            "accent": "#6fa8ff",
            "accent_soft": "rgba(111, 168, 255, 0.24)",
            "background": "radial-gradient(circle at top, rgba(56,92,196,.62), rgba(8,12,26,.96) 58%)",
            "winner_background": "linear-gradient(135deg, #20398d, #18295a 58%, #1a4f78)",
        },
    },
    {
        "slug": "game_show",
        "name": "Game Show",
        "description": "Bright spotlight colors, punchy reveal sounds, and a quick host-driven rhythm.",
        "reveal_sound": "confetti_hits",
        "flip_style": "clean_flip",
        "tick_sound_pack": "clean_clicks",
        "auto_advance_enabled": False,
        "auto_advance_seconds": 0,
        "submission_reveal_enabled": True,
        "submission_reveal_step_ms": 1300,
        "reveal_duration_ms": 5600,
        "theme": {
            "slug": "game_show",
            "name": "Game Show",
            "accent": "#ffd35c",
            "accent_soft": "rgba(255, 211, 92, 0.24)",
            "background": "radial-gradient(circle at top, rgba(170,110,18,.55), rgba(21,16,8,.96) 58%)",
            "winner_background": "linear-gradient(135deg, #7b4a10, #38220f 62%, #8c5e14)",
        },
    },
    {
        "slug": "family_party",
        "name": "Family Party",
        "description": "Bouncy family-friendly pacing with colorful pops and a slightly longer countdown.",
        "reveal_sound": "victory_chime",
        "flip_style": "party_bounce",
        "tick_sound_pack": "party_pops",
        "auto_advance_enabled": True,
        "auto_advance_seconds": 9,
        "submission_reveal_enabled": True,
        "submission_reveal_step_ms": 1700,
        "reveal_duration_ms": 6800,
        "theme": {
            "slug": "family_party",
            "name": "Family Party",
            "accent": "#ff7ecf",
            "accent_soft": "rgba(255, 126, 207, 0.22)",
            "background": "radial-gradient(circle at top, rgba(176,66,145,.55), rgba(23,11,25,.96) 58%)",
            "winner_background": "linear-gradient(135deg, #8b2d6f, #3c1737 62%, #8f4b29)",
        },
    },
    {
        "slug": "dramatic_finals",
        "name": "Dramatic Finals",
        "description": "Slower, more theatrical reveals with darker colors and tension-building audio.",
        "reveal_sound": "dramatic_rise",
        "flip_style": "dramatic_flip",
        "tick_sound_pack": "dramatic_ticks",
        "auto_advance_enabled": False,
        "auto_advance_seconds": 0,
        "submission_reveal_enabled": True,
        "submission_reveal_step_ms": 2100,
        "reveal_duration_ms": 7600,
        "theme": {
            "slug": "dramatic_finals",
            "name": "Dramatic Finals",
            "accent": "#b082ff",
            "accent_soft": "rgba(176, 130, 255, 0.22)",
            "background": "radial-gradient(circle at top, rgba(80,44,146,.52), rgba(11,8,19,.97) 58%)",
            "winner_background": "linear-gradient(135deg, #4b2a7f, #221533 62%, #653f8f)",
        },
    },
]

ROUND_THEMES = [
    {
        "slug": "midnight_arcade",
        "name": "Midnight Arcade",
        "accent": "#7c9cff",
        "accent_soft": "rgba(124, 156, 255, 0.22)",
        "background": "radial-gradient(circle at top, rgba(58,86,165,.55), rgba(10,14,24,.96) 58%)",
        "winner_background": "linear-gradient(135deg, #203271, #172641 62%, #18344d)",
    },
    {
        "slug": "emerald_spotlight",
        "name": "Emerald Spotlight",
        "accent": "#4fd49f",
        "accent_soft": "rgba(79, 212, 159, 0.22)",
        "background": "radial-gradient(circle at top, rgba(30,108,80,.55), rgba(9,13,16,.96) 58%)",
        "winner_background": "linear-gradient(135deg, #154f45, #112932 62%, #1f5847)",
    },
    {
        "slug": "sunset_hype",
        "name": "Sunset Hype",
        "accent": "#ffad5a",
        "accent_soft": "rgba(255, 173, 90, 0.22)",
        "background": "radial-gradient(circle at top, rgba(140,81,34,.55), rgba(16,12,10,.96) 58%)",
        "winner_background": "linear-gradient(135deg, #6f3a16, #2d1f17 62%, #704d1f)",
    },
    {
        "slug": "magenta_laser",
        "name": "Magenta Laser",
        "accent": "#d96cff",
        "accent_soft": "rgba(217, 108, 255, 0.22)",
        "background": "radial-gradient(circle at top, rgba(104,38,130,.55), rgba(14,10,20,.96) 58%)",
        "winner_background": "linear-gradient(135deg, #5d2474, #271736 62%, #4f2061)",
    },
]

DEFAULT_PROMPTS = [
    "My smart home broke because of ____.",
    "The weirdest automation I ever deployed was ____.",
    "Tonight's network outage was caused by ____.",
    "The best reward for winning chores is ____.",
    "My dashboard would be better with more ____.",
]

DEFAULT_WHITE_CARDS = [
    "bad YAML",
    "a mystery Zigbee ghost",
    "Cisco spanning tree",
    "an overcaffeinated automation",
    "too many dashboards",
    "a reboot that fixed everything",
    "the wrong VLAN",
    "an untested script",
    "a cursed Wi-Fi dead spot",
    "a surprise power outage",
    "three duplicate helpers",
    "copy-paste config",
    "an all-nighter in the server room",
    "voice assistant drama",
    "a forgotten cron job",
    "network loop chaos",
    "a stale DHCP lease",
    "the family group chat",
    "mDNS nonsense",
    "a suspicious firmware update",
]


PRESET_EXPORT_VERSION = 1
PRESET_EXPORT_KIND = "ha_card_game_theme_presets"


DECK_EXPORT_VERSION = 1
DECK_EXPORT_KIND = "ha_card_game_deck_packs"


GAME_MODE_CARDS = "cards"
GAME_MODE_TRIVIA = "trivia"

TRIVIA_CATEGORIES = [
    "history",
    "fun_facts",
    "geography",
    "movies",
    "1990s",
    "2000s",
    "2010s",
    "computer_games",
]

TRIVIA_AGE_RANGES = [
    "6_8",
    "9_12",
    "13_17",
    "18_plus",
]

TRIVIA_DIFFICULTY_BY_AGE = {
    "6_8": "easy",
    "9_12": "easy_medium",
    "13_17": "medium",
    "18_plus": "medium_hard",
}


PARENTAL_CONTENT_MODES = [
    "family_safe",
    "teen",
    "adult",
]
DEFAULT_PARENTAL_CONTROLS = {
    "enabled": True,
    "content_mode": "family_safe",
    "require_ai_approval": True,
    "allow_remote_players": False,
    "allowed_trivia_categories": list(TRIVIA_CATEGORIES),
}
AI_QUEUE_MAX_ITEMS = 50

AI_EXPORT_KIND = "ha_card_game_ai_content"
AI_EXPORT_VERSION = 1
DEFAULT_AI_MODEL = "gpt-5-codex"
DEFAULT_AI_ENDPOINT = "https://api.openai.com/v1/responses"
