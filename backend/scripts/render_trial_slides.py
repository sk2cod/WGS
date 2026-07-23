"""Task "#19" render verification -- POSTs real slide content (from
direct_write_schema_trial.py's saved JSON) to the local Next.js /api/render
route, so the cover's headline overflow risk and the closing's 2-4 sentence
fit can be checked against a REAL Satori render, not just word counts.
Requires `pnpm dev` running in frontend/ on localhost:3000."""

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
    "mindset-self-doubt",
    "career-boundaries",
    "wellness-stress-regulation",
    "inspiring-women-who-changed-history",
    "relationships-invisible-labor",
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


def main() -> None:
    for topic_id in TOPIC_IDS:
        path = os.path.join(SCRATCH_DIR, f"direct_write_trial_{topic_id}.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cover = data["slides"][0]
        closing = data["slides"][4]
        render("carousel_cover", cover, f"render_cover_{topic_id}.png")
        render("carousel_closing", closing, f"render_closing_{topic_id}.png")


if __name__ == "__main__":
    main()
