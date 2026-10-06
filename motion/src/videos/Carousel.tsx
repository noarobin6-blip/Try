import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FONTS } from "../fonts";
import { LOOKS } from "../looks";

// Proposition 3 — Instagram éditorial : carrousel en profondeur, une tenue au
// centre, les autres en retrait. Pause, rotation, pause… et la dernière rotation
// ramène la première tenue : la vidéo boucle sans couture.
type Props = {
  readonly title: string;
  readonly titleAccent: string;
  readonly kicker: string;
};

const HOLD = 1.0;
const MOVE = 0.6;
const FIGURE_HEIGHT = 1000;
const FLOOR_Y = 1400;
const ROTATE = Easing.bezier(0.7, 0, 0.2, 1);

export const Carousel: React.FC<Props> = ({ title, titleAccent, kicker }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const count = LOOKS.length;

  const stepFrames = (HOLD + MOVE) * fps;
  const step = Math.floor(frame / stepFrames);
  const local = frame - step * stepFrames;
  const move = interpolate(local, [HOLD * fps, stepFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ROTATE,
  });
  const current = step + move;

  // Légende : l'ancienne sort pendant la 1re moitié de la rotation, la nouvelle entre ensuite.
  const captionIndex = (move < 0.5 ? step : step + 1) % count;
  const captionOut = interpolate(move, [0, 0.5], [0, 1], {
    extrapolateRight: "clamp",
  });
  const captionIn = interpolate(move, [0.5, 1], [0, 1], {
    extrapolateLeft: "clamp",
  });
  const captionShift =
    move === 0 ? 0 : move < 0.5 ? -captionOut * 100 : (1 - captionIn) * 100;

  const items = LOOKS.map((look, i) => {
    let d = (((i - current) % count) + count) % count;
    if (d >= count / 2) {
      d -= count;
    }
    return { look, d };
  }).sort((a, b) => Math.abs(b.d) - Math.abs(a.d));

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse 80% 55% at 50% 52%, #FAF7F2 0%, #EAE3D8 70%, #E0D7CA 100%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 170,
          width: "100%",
          textAlign: "center",
          color: "#1A1A1A",
        }}
      >
        <div
          style={{
            fontFamily: FONTS.wide,
            fontWeight: 500,
            fontSize: 26,
            letterSpacing: 8,
          }}
        >
          {kicker}
        </div>
        <div style={{ marginTop: 10, lineHeight: 1 }}>
          <span
            style={{
              fontFamily: FONTS.wide,
              fontWeight: 900,
              fontSize: 112,
              letterSpacing: -3,
            }}
          >
            {title}
          </span>{" "}
          <span
            style={{
              fontFamily: FONTS.serif,
              fontStyle: "italic",
              fontSize: 132,
              marginLeft: 12,
            }}
          >
            {titleAccent}
          </span>
        </div>
      </div>

      <AbsoluteFill style={{ perspective: 2000 }}>
        {items.map(({ look, d }) => {
          const a = Math.abs(d);
          const side = Math.sign(d);
          const width = (look.width / look.height) * FIGURE_HEIGHT;
          const offsetX =
            side * interpolate(a, [0, 1, 2, 2.5], [0, 370, 640, 760]);
          const scale = interpolate(a, [0, 1, 2.5], [1, 0.7, 0.48]);
          return (
            <div
              key={look.src}
              style={{
                position: "absolute",
                left: 540 - width / 2,
                top: FLOOR_Y - FIGURE_HEIGHT,
                width,
                height: FIGURE_HEIGHT,
                transformOrigin: "50% 100%",
                translate: `${offsetX}px ${-a * 70}px`,
                scale,
                rotate: `y ${-d * 16}deg`,
                opacity: interpolate(a, [1.9, 2.4], [1, 0], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                }),
                filter: `brightness(${1 - a * 0.1}) saturate(${1 - a * 0.25}) blur(${a * 2.2}px)`,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: "8%",
                  right: "8%",
                  bottom: -26,
                  height: 56,
                  borderRadius: "50%",
                  background:
                    "radial-gradient(closest-side, rgba(40,28,15,0.30), rgba(40,28,15,0))",
                }}
              />
              <Img
                src={look.src}
                style={{ position: "absolute", width, height: FIGURE_HEIGHT }}
              />
            </div>
          );
        })}
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          top: 1450,
          width: "100%",
          height: 150,
          overflow: "hidden",
          textAlign: "center",
          color: "#1A1A1A",
        }}
      >
        <div
          style={{
            translate: `0px ${captionShift}%`,
            opacity: move < 0.5 ? 1 - captionOut : captionIn,
          }}
        >
          <div
            style={{
              fontFamily: FONTS.wide,
              fontWeight: 500,
              fontSize: 26,
              letterSpacing: 6,
            }}
          >
            N°{String(captionIndex + 1).padStart(2, "0")} /{" "}
            {String(count).padStart(2, "0")}
          </div>
          <div
            style={{
              fontFamily: FONTS.serif,
              fontStyle: "italic",
              fontSize: 80,
              lineHeight: 1.15,
            }}
          >
            {LOOKS[captionIndex].name}
          </div>
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          top: 1630,
          width: "100%",
          display: "flex",
          justifyContent: "center",
          gap: 12,
        }}
      >
        {LOOKS.map((look, i) => {
          let d = Math.abs(i - (current % count));
          d = Math.min(d, count - d);
          const active = interpolate(d, [0, 1], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div
              key={look.src}
              style={{
                height: 8,
                width: 16 + active * 40,
                borderRadius: 4,
                backgroundColor: `rgba(26,26,26,${0.25 + active * 0.75})`,
              }}
            />
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
