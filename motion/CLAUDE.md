# Projet vidéo `motion/` (Remotion)

Vidéos programmatiques en React, rendues en MP4/PNG. Remotion **4.0.533** — même version que les skills Remotion de `.claude/skills/`.

## Skills installées (`.claude/skills/`)

| Usage | Skills |
| --- | --- |
| Vidéo Remotion (point d'entrée : `remotion-best-practices`) | `remotion-create`, `remotion-markup`, `remotion-studio`, `remotion-render`, `remotion-captions`, `remotion-maps`, `remotion-interactivity`, `remotion-multimedia`, `remotion-saas`, `remotion-docs`, `remotion-upgrade` |
| Animation GSAP (officielles GreenSock) | `gsap-core`, `gsap-timeline`, `gsap-react`, `gsap-scrolltrigger`, `gsap-plugins`, `gsap-utils`, `gsap-performance`, `gsap-frameworks` |
| Goût / exigence motion (Emil Kowalski) | `emil-design-eng`, `animate`, `improve-animations`, `review-animations`, `animation-vocabulary`, `find-animation-opportunities` |
| Principes motion (Kowalski, Krehel, Tompkins) | `design-motion-principles` |

Sources : `remotion-dev/skills`, `greensock/gsap-skills`, `emilkowalski/skills`, `kylezantos/design-motion-principles` (GitHub).

## Règles de ce projet

- **Polices** : uniquement celles de `src/fonts.ts` (fichiers dans `public/fonts`). Ne pas utiliser `@remotion/google-fonts` : le navigateur de rendu n'a pas d'accès réseau dans la sandbox. Pour une nouvelle police, ajouter le `.woff2` (paquet npm `@fontsource/*`) dans `public/fonts` et l'enregistrer dans `src/fonts.ts`.
- **Assets** : images, sons, Lottie JSON dans `public/`, chargés via `staticFile()`. Pas d'URL distante au rendu. Les Lottie du dashboard sont dans `../assets/`.
- **Animation** : piloter tout par `useCurrentFrame()` (`spring`, `interpolate`, `@remotion/transitions`). GSAP seulement en timeline pausée et seekée sur la frame courante — jamais en lecture temps réel.
- **Navigateur** : `remotion.config.ts` utilise le headless shell de Playwright quand il est présent (le téléchargement Chrome de Remotion est bloqué ici).
- `SmokeTest` est une composition de vérification ; la remplacer par la vraie vidéo.

## Commandes

```bash
npm run dev                                        # Studio (aperçu)
npx remotion render <Id> out/video.mp4             # rendu MP4 (H.264, CRF 16)
npx remotion still <Id> out/frame.png --frame=30   # image fixe pour contrôle visuel
npm run lint                                       # eslint + tsc
```

Avant de livrer : rendre quelques stills à des frames clés et les regarder.
