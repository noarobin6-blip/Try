import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig } from "remotion";
import { FONTS } from "../fonts";
import { LOOKS } from "../looks";

// Proposition 1 — fidèle à la référence : les tenues défilent en continu de droite
// à gauche sur fond blanc, et le texte blanc ne se lit que là où il passe sur un
// vêtement. Une longueur de bande par durée de vidéo : la boucle est parfaite.
type Props = {
  readonly figureHeight: number;
  readonly top: number;
  readonly gap: number;
  readonly kicker: string;
  readonly title: string;
  readonly subtitle: string;
  readonly textCenterY: number;
};

export const Marquee: React.FC<Props> = ({
  figureHeight,
  top,
  gap,
  kicker,
  title,
  subtitle,
  textCenterY,
}) => {
  const frame = useCurrentFrame();
  const { width, durationInFrames } = useVideoConfig();

  const widths = LOOKS.map((l) => (l.width / l.height) * figureHeight);
  const stripLength = widths.reduce((sum, w) => sum + w + gap, 0);
  const offsets = widths.map((_, i) =>
    widths.slice(0, i).reduce((sum, w) => sum + w + gap, 0),
  );
  const copies = Math.ceil(width / stripLength) + 1;
  const scroll = (frame / durationInFrames) * stripLength;

  return (
    <AbsoluteFill style={{ backgroundColor: "#FFFFFF" }}>
      {Array.from({ length: copies }).flatMap((_, copy) =>
        LOOKS.map((look, i) => {
          const x = copy * stripLength + offsets[i] - scroll;
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
                top,
                height: figureHeight,
                width: widths[i],
                translate: `${x}px 0px`,
              }}
            />
          );
        }),
      )}
      <AbsoluteFill
        style={{
          top: textCenterY - 200,
          height: 400,
          justifyContent: "center",
          alignItems: "center",
          color: "#FFFFFF",
          fontFamily: FONTS.wide,
          textAlign: "center",
          gap: 14,
        }}
      >
        <div style={{ fontSize: 58, fontWeight: 300, letterSpacing: 2 }}>
          {kicker}
        </div>
        <div
          style={{
            fontSize: 132,
            fontWeight: 900,
            letterSpacing: -2,
            lineHeight: 1,
          }}
        >
          {title}
        </div>
        <div style={{ fontSize: 58, fontWeight: 300, letterSpacing: 2 }}>
          {subtitle}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
