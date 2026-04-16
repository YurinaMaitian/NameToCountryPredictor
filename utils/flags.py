# utils/flags.py
COUNTRY_FLAGS = {
    "American": "🇺🇸",
    "Arabic": "🇸🇦",
    "British": "🇬🇧",
    "Chinese": "🇨🇳",
    "Dutch": "🇳🇱",
    "French": "🇫🇷",
    "German": "🇩🇪",
    "Indian": "🇮🇳",
    "Italian": "🇮🇹",
    "Japanese": "🇯🇵",
    "Korean": "🇰🇷",
    "Polish": "🇵🇱",
    "Portuguese": "🇵🇹",
    "Russian": "🇷🇺",
    "Spanish": "🇪🇸",
    "Vietnamese": "🇻🇳",
}


def get_flag(country_name: str) -> str:
    return COUNTRY_FLAGS.get(country_name, "🏳️")
