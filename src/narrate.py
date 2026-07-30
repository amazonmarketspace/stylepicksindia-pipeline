#!/usr/bin/env python3
"""
Generates Hindi voiceover per card with edge-tts.
Voice: hi-IN-SwaraNeural (Female, Hindi, Indian)
Speed: +28%
Category: Smartphones and smartphone accessories
"""
import asyncio, json, sys, subprocess
from pathlib import Path

VOICE = "hi-IN-SwaraNeural"
RATE  = "+28%"
ROOT  = Path(__file__).resolve().parent.parent

# Category-aware intro hooks
CATEGORY_INTROS = {
    "smartphone": "यह स्मार्टफोन है",
    "phone": "यह स्मार्टफोन है",
    "charger": "यह एक शानदार चार्जर है",
    "powerbank": "यह पावर बैंक है",
    "car": "यह कार चार्जर है",
    "cable": "यह केबल है",
    "earphone": "यह ईयरफोन है",
    "case": "यह फोन केस है",
    "default": "यह प्रोडक्ट है",
}


def category_intro(p: dict) -> str:
    cat = p.get("category", "").lower()
    for key, intro in CATEGORY_INTROS.items():
        if key in cat:
            return intro
    return CATEGORY_INTROS["default"]


def line_long_hi(p, i, n):
    d = ""
    if p.get("discount"):
        d = (f" इसकी असली कीमत {int(p['mrp'])} रुपये थी, "
             f"अब सिर्फ {int(p['price'])} रुपये में मिल रहा है — "
             f"यानी {p['discount']} प्रतिशत की छूट।")
    return (
        f"नंबर {i}। {p['brand']} का {p['name']}। "
        f"{p['hook']}। "
        f"{p['feature_1']}। "
        f"{p['feature_2']}। "
        f"{p['feature_3']}।"
        f"{d} "
        f"{p['verdict']}।"
    )


def line_short_hi(p):
    d = f", {p['discount']} प्रतिशत की छूट" if p.get("discount") else ""
    return (
        f"{p['hook']}। "
        f"{p['brand']} {p['name']}। "
        f"{p['feature_1']}। "
        f"कीमत सिर्फ {int(p['price'])} रुपये{d}। "
        f"Description में लिंक है।"
    )


async def say(text, out: Path):
    import edge_tts
    mp3 = out.with_suffix(".mp3")
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(mp3))
    subprocess.run(["ffmpeg", "-y", "-i", str(mp3), "-ar", "44100", str(out)],
                   check=True, capture_output=True)
    mp3.unlink()


async def main():
    ds = sorted((ROOT / "out").glob("*/manifest.json"))
    if not ds:
        sys.exit("Run build.py first.")
    d = ds[-1].parent
    ps = json.loads((d / "manifest.json").read_text())
    (d / "audio").mkdir(exist_ok=True)
    for i, p in enumerate(ps, 1):
        await say(line_long_hi(p, i, len(ps)), d / "audio" / f"{i:02d}.wav")
        await say(line_short_hi(p), d / "audio" / f"short_{i:02d}.wav")
        print(f"narrated {i}/{len(ps)}: {p['name']}")


if __name__ == "__main__":
    asyncio.run(main())
