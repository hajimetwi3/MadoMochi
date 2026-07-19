"""
UI strings for the buddy — English and Japanese.

The default language follows the Windows display language (Japanese
Windows -> ja, everything else -> en); picking one from the right-click
menu pins it in config.json. Adding a language is one more dict here.
"""

from __future__ import annotations

import ctypes

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "badge_alert": "WAITING",
        # mood one-liners (right-click demo rows)
        "speech_idle": "standing by — call me",
        "speech_listen": "listening...",
        "speech_think": "thinking...",
        "speech_work": "working...",
        "speech_happy": "done! yay",
        "speech_error": "stumbled...",
        "speech_alert": "needs your OK!",
        "speech_sleep": "good night zzz",
        # right-click menu
        "demo_walk": "Walk demo",
        "demo_gym": "Gym demo",
        "demo_soccer": "Soccer demo",
        "demo_roam": "Roam demo (neglected alert)",
        "skins": "Skins",
        "bgm_menu": "🎵 Retro BGM",
        "bgm_on": "Turn BGM on",
        "bgm_off": "Turn BGM off",
        "bgm_volume": "Volume (now: {pct}%)",
        "bgm_follow_on": "Turn mood-picked tracks on",
        "bgm_follow_off": "Turn mood-picked tracks off",
        "se_on": "Turn sound effects on",
        "se_off": "Turn sound effects off",
        "led_on": "Turn LED on",
        "led_off": "Turn LED off",
        "led_pattern": "LED pattern (now: {mode})",
        "led_auto": "auto (follow mood)",
        "reset_pos": "Reset position (Claude bottom-right)",
        "follow_on": "Turn window-follow on",
        "follow_off": "Turn window-follow off",
        "park_on": "Turn corner parking on",
        "park_off": "Turn corner parking off",
        "badge_mode": "Badge (now: {mode})",
        "topmost_on": "Always on top: ON",
        "topmost_off": "Always on top: OFF",
        "settings": "Settings…",
        "quit": "Quit",
        # settings dialog
        "settings_title": "MadoMochi Settings",
        "set_scale": "Size (scale)",
        "set_walk": "Seconds until idle walk",
        "set_premium": "Premium move interval, avg (s)",
        "set_roam": "Screen-roam after waiting (s)",
        "btn_reset": "Reset to defaults",
        "btn_close": "Close (save)",
        "show_label": "Showcase demo — runs everything, with sound (for GIFs)",
        "show_btn": "{n}s",
        "show_stop": "Stop",
        "show_roam": "Include roaming (leaves the frame)",
    },
    "ja": {
        "badge_alert": "確認待ち",
        "speech_idle": "待機中 — 呼んでね",
        "speech_listen": "受信中…",
        "speech_think": "考えてる…",
        "speech_work": "作業中…",
        "speech_happy": "完了！やったー",
        "speech_error": "つまずいた…",
        "speech_alert": "確認してほしいかも！",
        "speech_sleep": "おやすみ zzz",
        "demo_walk": "お散歩デモ",
        "demo_gym": "筋トレデモ",
        "demo_soccer": "サッカーデモ",
        "demo_roam": "うろうろデモ（確認待ち放置）",
        "skins": "スキン",
        "bgm_menu": "🎵 レトロBGM",
        "bgm_on": "BGM ON にする",
        "bgm_off": "BGM OFF にする",
        "bgm_volume": "音量（今: {pct}%）",
        "bgm_follow_on": "気分で曲変更 ON にする",
        "bgm_follow_off": "気分で曲変更 OFF にする",
        "se_on": "効果音 ON にする",
        "se_off": "効果音 OFF にする",
        "led_on": "LED ON にする",
        "led_off": "LED OFF にする",
        "led_pattern": "LED パターン（今: {mode}）",
        "led_auto": "auto（気分連動）",
        "reset_pos": "位置をリセット（Claude右下）",
        "follow_on": "ウィンドウ追従 ON にする",
        "follow_off": "ウィンドウ追従 OFF にする",
        "park_on": "右隅居座りモード ON にする",
        "park_off": "右隅居座りモード OFF にする",
        "badge_mode": "バッジ表示（今: {mode}）",
        "topmost_on": "最前面 ON",
        "topmost_off": "最前面 OFF",
        "settings": "設定…",
        "quit": "終了",
        "settings_title": "MadoMochi 設定",
        "set_scale": "サイズ（スケール）",
        "set_walk": "お散歩までの秒数",
        "set_premium": "プレミア動作の平均間隔（秒）",
        "set_roam": "確認待ちのうろうろ開始（秒）",
        "btn_reset": "デフォルトに戻す",
        "btn_close": "閉じる（保存）",
        "show_label": "全体デモショー — 全アクション＋音を自動上演（GIF撮影用）",
        "show_btn": "{n}秒",
        "show_stop": "停止",
        "show_roam": "うろうろも台本に入れる（画面を離れます）",
    },
}

# shown untranslated on purpose — each language names itself
LANG_LABEL = {"en": "English", "ja": "日本語"}


def detect_lang() -> str:
    """Follow the Windows display language: Japanese -> ja, else en."""
    try:
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if langid & 0x3FF == 0x11:  # LANG_JAPANESE
            return "ja"
    except Exception:
        pass
    return "en"


def tr(lang: str, key: str, **fmt) -> str:
    """Translate a key; unknown languages and keys fall back gracefully."""
    table = STRINGS.get(lang) or STRINGS["en"]
    s = table.get(key) or STRINGS["en"].get(key, key)
    return s.format(**fmt) if fmt else s
