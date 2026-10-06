import {
  AbsoluteFill,
  Img,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { LOOKS } from "../looks";

// Copie conforme de la vidéo de référence, mesurée image par image :
// 4:3, 30 i/s, silhouettes coupées au cou et pieds au ras du bas sur toute la
// hauteur, corps espacés à intervalle régulier, défilement
// linéaire vers la gauche de 10,04 px par image pour 905 px de haut.
// La durée couvre deux longueurs de bande : la vidéo boucle sans raccord.
// Fond : dégradé lavande reconstruit par scripts/fond.py.
export const REFERENCE_SPEED = 10.04 / 905;
const LOOPS = 2;

export const durationFor = (height: number) =>
  Math.round((LOOPS * stripLength(height)) / (REFERENCE_SPEED * height));

const stripLength = (height: number) =>
  LOOKS.reduce((sum, l) => sum + (l.pitch * height) / l.height, 0);

export const Defile: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();

  const length = stripLength(height);
  const centers = LOOKS.map((_, i) =>
    LOOKS.slice(0, i).reduce((sum, l) => sum + (l.pitch * height) / l.height, 0),
  );
  const scroll = ((frame / durationInFrames) * LOOPS * length) % length;
  const copies = Math.ceil(width / length) + 2;

  return (
    <AbsoluteFill style={{ backgroundColor: "#7D72C0" }}>
      <Img
        src={staticFile("fond.png")}
        style={{ position: "absolute", width, height }}
      />
      {Array.from({ length: copies }).flatMap((_, copy) =>
        LOOKS.map((look, i) => {
          const scale = height / look.height;
          const w = look.width * scale;
          // Position entière : l'image reste au pixel près, donc parfaitement nette.
          const x = Math.round(
            (copy - 1) * length + centers[i] - look.center * scale - scroll,
          );
          if (x > width || x + w < 0) {
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
                width: w,
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
