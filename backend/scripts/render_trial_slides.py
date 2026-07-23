"""Task "#19" render verification, extended for task "#23" -- POSTs real (and,
for #23, synthetic boundary-length) slide content to the local Next.js
/api/render route, so layout/typography changes can be checked against a real
Satori render, not just word counts. Requires `pnpm dev` running in frontend/
on localhost:3000."""

import json
import os
import urllib.error
import urllib.request

SCRATCH_DIR = r"C:\Users\saurabh.k\AppData\Local\Temp\claude\C--Users-saurabh-k-PycharmProjects-PythonProject-WGS\b5847c58-0210-472f-9293-f481adbab38f\scratchpad"

WISDOM_TOKENS = {
    "primary": "#4B3A6E",
    "secondary": "#F3EEF9",
    "accent": "#8A63D2",
    "text_color": "#241C33",
    "background_color": "#FAF7FC",
    "font_heading": "Archivo Black",
    "font_script": "Alex Brush",
    "font_body": "Inter",
}
MASTHEAD = {"masthead_short": "WGS", "category": "MINDSET", "number": "01"}

TOPIC_IDS = [
    "career-imposter-syndrome",
    "wellness-burnout",
]


def render(template_id: str, slide: dict, out_name: str) -> None:
    body = {
        "template_id": template_id,
        "slides": [slide],
        "masthead": MASTHEAD,
        "tokens": WISDOM_TOKENS,
        "hero_image_url": None,
    }
    out_path = os.path.join(SCRATCH_DIR, out_name)
    req = urllib.request.Request(
        "http://localhost:3000/api/render",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        print(f"FAILED {out_name}: {e.code} {e.read()[:500]}")
        return
    if status != 200:
        print(f"FAILED {out_name}: {status}")
        return
    with open(out_path, "wb") as f:
        f.write(content)
    print(f"OK {out_name}: {len(content)} bytes -> {out_path}")


def render_real_trials() -> None:
    for topic_id in TOPIC_IDS:
        path = os.path.join(SCRATCH_DIR, f"direct_write_trial_{topic_id}.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        render("carousel_cover", data["slides"][0], f"s23_real_cover_{topic_id}.png")
        for i in (1, 2, 3):
            render("carousel_body_teaching", data["slides"][i], f"s23_real_body{i}_{topic_id}.png")
        render("carousel_closing", data["slides"][4], f"s23_real_closing_{topic_id}.png")
        render("carousel_conversation", data["slides"][5], f"s23_real_conversation_{topic_id}.png")


_VOCAB = [
    "quiet", "morning", "steady", "hands", "gather", "light", "before", "anyone",
    "asks", "for", "more", "than", "she", "has", "left", "to", "give", "today",
    "and", "still", "the", "room", "waits", "on", "her", "to", "explain", "why",
]


def make_text(n_words: int) -> str:
    """Builds real-looking prose at an EXACT word count, with periods/commas
    glued onto existing word tokens (never inserted as separate tokens), so
    `len(text.split())` always equals n_words regardless of punctuation --
    verified below via an assertion, not assumed."""
    tokens = [_VOCAB[i % len(_VOCAB)] for i in range(n_words)]
    for i in range(len(tokens)):
        position = i + 1
        if position == n_words:
            continue
        if position % 12 == 0:
            tokens[i] += "."
        elif position % 5 == 0:
            tokens[i] += ","
    text = " ".join(tokens)
    if not text.endswith("."):
        text += "."
    assert len(text.split()) == n_words, f"expected {n_words} words, got {len(text.split())}"
    return text


def render_boundary_synthetics() -> None:
    """Task "#23": both ends of each template's real word range, as exact,
    verified word counts -- not LLM calls, so these don't count against the
    2-real-trial limit (that limit governs API usage, not local Satori renders)."""
    # carousel_cover: _CAROUSEL_DIRECT_COVER_WORD_RANGE (20, 45), tolerant (18, 50) --
    # combined across headline + cover_body.
    headline_floor = "A short floor headline"  # 4 words
    cover_body_floor = make_text(14)  # 4 + 14 = 18 (floor)
    print(f"cover floor: headline={len(headline_floor.split())} + body={len(cover_body_floor.split())} = {len(headline_floor.split()) + len(cover_body_floor.split())}")
    render(
        "carousel_cover",
        {
            "template_id": "carousel_cover",
            "headline_word": headline_floor,
            "script_word": "",
            "kicker": "",
            "cover_body": cover_body_floor,
        },
        "s23_synth_cover_floor.png",
    )
    headline_ceiling = "A much longer ceiling headline phrase"  # 6 words
    cover_body_ceiling = make_text(44)  # 6 + 44 = 50 (ceiling)
    print(f"cover ceiling: headline={len(headline_ceiling.split())} + body={len(cover_body_ceiling.split())} = {len(headline_ceiling.split()) + len(cover_body_ceiling.split())}")
    render(
        "carousel_cover",
        {
            "template_id": "carousel_cover",
            "headline_word": headline_ceiling,
            "script_word": "",
            "kicker": "",
            "cover_body": cover_body_ceiling,
        },
        "s23_synth_cover_ceiling.png",
    )

    # carousel_body_teaching: (35, 50), tolerant (31, 55) -- body text alone.
    body_floor = make_text(31)
    print(f"body floor: {len(body_floor.split())} words")
    render(
        "carousel_body_teaching",
        {"template_id": "carousel_body_teaching", "heading": "", "body": body_floor, "accent_phrase": "quiet morning steady"},
        "s23_synth_body_floor.png",
    )
    body_ceiling = make_text(55)
    print(f"body ceiling: {len(body_ceiling.split())} words")
    render(
        "carousel_body_teaching",
        {"template_id": "carousel_body_teaching", "heading": "", "body": body_ceiling, "accent_phrase": "quiet morning steady"},
        "s23_synth_body_ceiling.png",
    )

    # carousel_closing: _CAROUSEL_DIRECT_CLOSING_WORD_RANGE (24, 55), tolerant (21, 61).
    closing_floor = make_text(21)
    print(f"closing floor: {len(closing_floor.split())} words")
    render(
        "carousel_closing",
        {"template_id": "carousel_closing", "takeaway": closing_floor, "signature": "with you,"},
        "s23_synth_closing_floor.png",
    )
    closing_ceiling = make_text(61)
    print(f"closing ceiling: {len(closing_ceiling.split())} words")
    render(
        "carousel_closing",
        {"template_id": "carousel_closing", "takeaway": closing_ceiling, "signature": "with you,"},
        "s23_synth_closing_ceiling.png",
    )

    # carousel_conversation: (15, 25), tolerant (13, 28) -- question field only.
    # make_text() always ends with "." on the last token -- swap it for "?" so
    # the word count stays exact while the field reads as a real question.
    question_floor = make_text(13)[:-1] + "?"
    print(f"conversation floor: {len(question_floor.split())} words")
    render(
        "carousel_conversation",
        {
            "template_id": "carousel_conversation",
            "label": "- Conversation for today",
            "question": question_floor,
            "invite": "I'd love to hear it.",
            "cta": "Follow us for daily reminders that help you grow.",
            "handle": "@womensgrowthsociety",
        },
        "s23_synth_conversation_floor.png",
    )
    question_ceiling = make_text(28)[:-1] + "?"
    print(f"conversation ceiling: {len(question_ceiling.split())} words")
    render(
        "carousel_conversation",
        {
            "template_id": "carousel_conversation",
            "label": "- Conversation for today",
            "question": question_ceiling,
            "invite": "I'd love to hear it.",
            "cta": "Follow us for daily reminders that help you grow.",
            "handle": "@womensgrowthsociety",
        },
        "s23_synth_conversation_ceiling.png",
    )


if __name__ == "__main__":
    render_real_trials()
    render_boundary_synthetics()
