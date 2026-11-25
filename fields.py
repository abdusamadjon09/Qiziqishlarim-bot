import re

# soha kaliti -> (nomi, kalit so'zlar)
FIELDS = {
    "it": ("💻 IT va Dasturlash", ["python", "dastur", "kod", "web", "sayt", "it", "java", "kompyuter", "app", "bot", "c++", "ai", "robot", "gadget"]),
    "cyber": ("🛡 Kiber xavfsizlik", ["kiber", "xavfsiz", "hack", "xaker", "security", "cyber", "tarmoq"]),
    "design": ("🎨 Dizayn va ijod", ["dizayn", "rasm", "chizish", "video", "montaj", "foto", "ijod", "grafik", "animatsiya", "figma"]),
    "lang": ("🌍 Tillar", ["ingliz", "til", "rus", "arab", "koreys", "turk", "nemis", "english", "xitoy", "yapon"]),
    "sport": ("⚽ Sport", ["futbol", "sport", "voleybol", "boks", "kurash", "shaxmat", "basketbol", "suzish", "gym", "fitnes", "taekwondo"]),
    "books": ("📚 Kitob va adabiyot", ["kitob", "she'r", "sher", "yozish", "adabiyot", "o'qish", "roman", "hikoya"]),
    "music": ("🎵 Musiqa", ["musiqa", "gitara", "qo'shiq", "qoshiq", "piano", "kuy", "xonanda", "doira"]),
    "science": ("🔬 Fan va olimpiada", ["matem", "fizika", "kimyo", "biolog", "olimpiada", "fan", "astronom", "geograf", "tarix"]),
    "business": ("💼 Biznes", ["biznes", "savdo", "marketing", "startap", "pul", "iqtisod", "tadbirkor"]),
    "other": ("✨ Boshqa", []),
}


def classify(text: str) -> list[str]:
    """Qiziqishlar matnidan sohalarni aniqlaydi."""
    tokens = re.findall(r"[\w'ʻ’`]+", (text or "").lower())
    found = []
    for key, (_, kws) in FIELDS.items():
        for kw in kws:
            if any((t == kw) if len(kw) <= 3 else t.startswith(kw) for t in tokens):
                found.append(key)
                break
    return found or ["other"]


def extract(text: str) -> dict[str, str]:
    """Qiziqishlar matnidan sohalarni ajratadi: {kalit: nom}.
    Tanish sohalar tayyor guruhga, yangi (noma'lum) qiziqishlar esa o'zining yangi soha guruhiga aylanadi."""
    out: dict[str, str] = {}
    for item in [x.strip() for x in re.split(r"[,;\n]+", text or "") if x.strip()][:10]:
        known = [k for k in classify(item) if k != "other"]
        if known:
            for k in known:
                out[k] = FIELDS[k][0]
        else:
            slug = re.sub(r"[^\w']+", "-", item.lower()).strip("-")[:40]
            if slug:
                out[slug] = "🔹 " + item[:40].capitalize()
    return out or {"other": FIELDS["other"][0]}
