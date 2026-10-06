import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig } from "remotion";
import { LOOKS } from "../looks";

// Copie conforme de la vidéo de référence, mesurée image par image :
// 4:3, 30 i/s, silhouettes coupées au menton et pieds au ras du bas sur toute la
// hauteur, collées les unes aux autres, fond blanc cassé, défilement linéaire vers
// la gauche de 10,04 px par image pour 905 px de haut (≈ 1,11 % de la hauteur).
// La durée couvre deux longueurs de bande : la vidéo boucle sans raccord visible.
export const REFERENCE_SPEED = 10.04 / 905;

export const stripLength = (height: number) =>
  LOOKS.reduce((sum, l) => sum + (l.width / l.height) * height, 0);

export const Defile: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();

  const widths = LOOKS.map((l) => (l.width / l.height) * height);
  const length = stripLength(height);
  const offsets = widths.map((_, i) =>
    widths.slice(0, i).reduce((sum, w) => sum + w, 0),
  );
  const loops = Math.round(
    (durationInFrames * REFERENCE_SPEED * height) / length,
  );
  const scroll = ((frame / durationInFrames) * loops * length) % length;
  const copies = Math.ceil(width / length) + 1;

  return (
    <AbsoluteFill style={{ backgroundColor: "#FAF7FA" }}>
      {Array.from({ length: copies }).flatMap((_, copy) =>
        LOOKS.map((look, i) => {
          const x = copy * length + offsets[i] - scroll;
          if (x > width || x + widths[i] < 0) {
            return null;
          }
          return (
            <Img
              key={`${copy}-${i}`}
              src={look.src}
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                width: widths[i],
                height,
                translate: `${x}px 0px`,
              }}
            />
          );
        }),
      )}
    </AbsoluteFill>
  );
};
