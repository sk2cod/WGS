import type { BrandKit } from "./types";

// Locked WGS values — Section 6 of implementation-guide.md / Section 4 of the blueprint.
export const WGS_BRAND_KIT: BrandKit = {
  brand_name: "Women's Growth Society",
  handle: "@womensgrowthsociety",
  masthead_short: "WGS",
  niche:
    "Practical emotional intelligence and confidence-building for women " +
    "unlearning people-pleasing and navigating career and self-worth.",
  audience:
    "Women in their 20s-40s building a career while learning to trust " +
    "themselves, and craving steady, honest encouragement over empty positivity.",

  voice_traits: ["supportive", "trusted", "encouraging", "calm", "grounded-in-facts"],
  voice_samples: {
    poetic: [
      "You don't have to shrink to keep the peace. Some rooms were never meant to hold all of you.",
      "The tears you're hiding today are just proof you're finally listening to yourself.",
      "Growth doesn't announce itself. It just quietly becomes the way you breathe.",
      "You're allowed to outgrow people who only ever loved the smaller version of you.",
      "Some days strength looks like getting up. Other days, it looks like finally resting.",
    ],
    // Revised 2026-07-15 (logbook #30) — see docs/blueprint.md Section 4.
    direct: [
      "Rest isn't something you earn after you collapse. It's maintenance you schedule before your body forces the issue.",
      "Your cycle isn't an inconvenience you push through. It's data about your body you're free to actually use.",
      "Saying less to someone isn't cold. It's what happens once you stop over-explaining a decision that was already final.",
      "Research shows women are socialized to soften their opinions before they've even finished stating them. Naming the pattern doesn't undo it — but it's the first thing that has to happen.",
      "Confidence isn't a feeling you wait for. It's a skill you build one uncomfortable choice at a time.",
    ],
  },
  forbidden: [
    "preachy",
    "bossy",
    "negative",
    "overly corporate",
    "fake positivity",
    "clickbait",
    "hustle-mindset language",
    "engagement-bait CTAs (e.g. 'comment ❤️ if...')",
  ],

  mood_palettes: {
    wisdom: { primary: "#4B3A6E", secondary: "#F3EEF9", accent: "#8A63D2" },
    bold: { primary: "#8C3B2E", secondary: "#F7E9DE", accent: "#D9643F" },
    celebratory: { primary: "#6E4F17", secondary: "#FCEDB8", accent: "#E8A23D" },
  },
  text_color: "#241C33",
  background_color: "#FAF7FC",
  font_heading: "Archivo Black",
  font_script: "Alex Brush",
  font_body: "Inter",

  default_tone: ["warm", "encouraging"],
  signature_cta: "Follow us for daily reminders that help you grow.",
};
