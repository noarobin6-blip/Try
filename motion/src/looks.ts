import { staticFile } from "remotion";
import data from "./looks.json";

// Tenues préparées par scripts/preparer_tenues.py : PNG détourés et étalonnés
// à la hauteur de rendu, centre du corps (milieu des pieds, en px) et pas
// jusqu'à la tenue suivante (en px), calé sur le rythme de la référence.
export type Look = {
  readonly src: string;
  readonly width: number;
  readonly height: number;
  readonly center: number;
  readonly pitch: number;
};

export const LOOKS: readonly Look[] = data.map((look) => ({
  src: staticFile(look.file),
  width: look.width,
  height: look.height,
  center: look.center,
  pitch: look.pitch,
}));
