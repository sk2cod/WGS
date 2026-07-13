import { readFile } from "node:fs/promises";
import path from "node:path";

const FONTS_DIR = path.join(process.cwd(), "public", "fonts");

export interface SatoriFont {
  name: string;
  data: Buffer;
  weight?: 400 | 500 | 600 | 700;
  style?: "normal" | "italic";
}

let cached: SatoriFont[] | null = null;

/** Loads the same self-hosted TTFs the browser preview uses, for Satori's ImageResponse. */
export async function loadSlideFonts(): Promise<SatoriFont[]> {
  if (cached) return cached;

  const [archivoBlack, alexBrush, interRegular, interMedium, interSemiBold, interBold] =
    await Promise.all([
      readFile(path.join(FONTS_DIR, "ArchivoBlack-Regular.ttf")),
      readFile(path.join(FONTS_DIR, "AlexBrush-Regular.ttf")),
      readFile(path.join(FONTS_DIR, "Inter-Regular.ttf")),
      readFile(path.join(FONTS_DIR, "Inter-Medium.ttf")),
      readFile(path.join(FONTS_DIR, "Inter-SemiBold.ttf")),
      readFile(path.join(FONTS_DIR, "Inter-Bold.ttf")),
    ]);

  cached = [
    { name: "Archivo Black", data: archivoBlack, weight: 400, style: "normal" },
    { name: "Alex Brush", data: alexBrush, weight: 400, style: "normal" },
    { name: "Inter", data: interRegular, weight: 400, style: "normal" },
    { name: "Inter", data: interMedium, weight: 500, style: "normal" },
    { name: "Inter", data: interSemiBold, weight: 600, style: "normal" },
    { name: "Inter", data: interBold, weight: 700, style: "normal" },
  ];
  return cached;
}
