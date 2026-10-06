import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Polices embarquées dans public/fonts (sous-ensemble latin, accents FR inclus).
// Locales plutôt que Google Fonts : rendu identique hors-ligne et en sandbox.
type Face = {
  family: string;
  file: string;
  weight: string;
  style?: "normal" | "italic";
};

const FACES: Face[] = [
  ...["400", "500", "600", "700", "800", "900"].map((weight) => ({
    family: "Inter",
    file: `inter-latin-${weight}-normal.woff2`,
    weight,
  })),
  { family: "Inter", file: "inter-latin-400-italic.woff2", weight: "400", style: "italic" },
  ...["400", "500", "700"].map((weight) => ({
    family: "Space Grotesk",
    file: `space-grotesk-latin-${weight}-normal.woff2`,
    weight,
  })),
  { family: "Instrument Serif", file: "instrument-serif-latin-400-normal.woff2", weight: "400" },
  { family: "Instrument Serif", file: "instrument-serif-latin-400-italic.woff2", weight: "400", style: "italic" },
  ...["400", "700"].map((weight) => ({
    family: "JetBrains Mono",
    file: `jetbrains-mono-latin-${weight}-normal.woff2`,
    weight,
  })),
  ...["400", "700", "900"].map((weight) => ({
    family: "Playfair Display",
    file: `playfair-display-latin-${weight}-normal.woff2`,
    weight,
  })),
];

for (const face of FACES) {
  loadFont({
    family: face.family,
    url: staticFile(`fonts/${face.file}`),
    weight: face.weight,
    style: face.style ?? "normal",
    format: "woff2",
  });
}

export const FONTS = {
  sans: "Inter, sans-serif",
  display: "'Space Grotesk', Inter, sans-serif",
  serif: "'Instrument Serif', 'Playfair Display', serif",
  editorial: "'Playfair Display', serif",
  mono: "'JetBrains Mono', monospace",
} as const;
