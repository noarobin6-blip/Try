import { staticFile } from "remotion";

// Les 5 tenues détourées (public/looks, PNG transparents de 2000 px de haut).
// Les points des étiquettes sont en fractions de l'image : x 0 = gauche, y 0 = cou.
export type Tag = {
  readonly label: string;
  readonly x: number;
  readonly y: number;
};

export type Look = {
  readonly src: string;
  readonly width: number;
  readonly height: number;
  readonly name: string;
  readonly color: string;
  readonly tags: readonly Tag[];
};

export const LOOKS: readonly Look[] = [
  {
    src: staticFile("looks/look1.png"),
    width: 703,
    height: 2000,
    name: "Velours rose",
    color: "#BFE1F7",
    tags: [
      { label: "Zip velours", x: 0.46, y: 0.12 },
      { label: "Sac fourrure", x: 0.8, y: 0.2 },
      { label: "Flare velours", x: 0.28, y: 0.6 },
    ],
  },
  {
    src: staticFile("looks/look2.png"),
    width: 630,
    height: 2000,
    name: "Caraco & crayon",
    color: "#F4A9C6",
    tags: [
      { label: "Caraco crème", x: 0.4, y: 0.12 },
      { label: "Sac monogramme", x: 0.82, y: 0.17 },
      { label: "Jupe crayon", x: 0.3, y: 0.46 },
    ],
  },
  {
    src: staticFile("looks/look3.png"),
    width: 638,
    height: 2000,
    name: "Dentelle & anis",
    color: "#CBB8F2",
    tags: [
      { label: "Caraco dentelle", x: 0.34, y: 0.13 },
      { label: "Sac baguette", x: 0.79, y: 0.17 },
      { label: "Jupe asymétrique", x: 0.3, y: 0.42 },
    ],
  },
  {
    src: staticFile("looks/look4.png"),
    width: 588,
    height: 2000,
    name: "Pastel & denim",
    color: "#F6DE7E",
    tags: [
      { label: "Top imprimé", x: 0.36, y: 0.14 },
      { label: "Mini sac", x: 0.84, y: 0.08 },
      { label: "Jean taille basse", x: 0.3, y: 0.55 },
    ],
  },
  {
    src: staticFile("looks/look5.png"),
    width: 671,
    height: 2000,
    name: "Polo & dentelle",
    color: "#FF9A6E",
    tags: [
      { label: "Polo rayé", x: 0.32, y: 0.22 },
      { label: "Sac monogramme", x: 0.84, y: 0.2 },
      { label: "Jupon dentelle", x: 0.43, y: 0.49 },
      { label: "Bottes biker", x: 0.36, y: 0.85 },
    ],
  },
];
