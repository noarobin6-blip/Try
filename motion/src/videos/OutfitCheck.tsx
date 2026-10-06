import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FONTS } from "../fonts";
import { Look, LOOKS } from "../looks";

// Proposition 2 — TikTok « lequel tu prends ? » : accroche avec les 5 tenues,
// une tenue par temps fort (coupe franche), étiquettes des pièces, puis appel à
// commenter. Pensé pour un son à ~120 BPM : 1,5 s = 3 temps par tenue.
type Props = {
  readonly hookTitle: string;
  readonly hookQuestion: string;
  readonly endTitle: string;
  readonly endSubtitle: string;
};

const HOOK = 1.5;
const PER_LOOK = 1.5;

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);
const POP = Easing.bezier(0.34, 1.56, 0.64, 1);

export const OutfitCheck: React.FC<Props> = ({
  hookTitle,
  hookQuestion,
  endTitle,
  endSubtitle,
}) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#F3EFE7" }}>
      <Sequence name="Accroche" durationInFrames={HOOK * fps} premountFor={fps}>
        <Lineup
          background="#F3EFE7"
          ink="#111111"
          title={hookTitle}
          subtitle={hookQuestion}
        />
      </Sequence>
      {LOOKS.map((look, i) => (
        <Sequence
          key={look.src}
          name={`Look ${i + 1}`}
          from={(HOOK + i * PER_LOOK) * fps}
          durationInFrames={PER_LOOK * fps}
          premountFor={fps}
        >
          <LookScene look={look} index={i} />
        </Sequence>
      ))}
      <Sequence
        name="Fin"
        from={(HOOK + LOOKS.length * PER_LOOK) * fps}
        premountFor={fps}
      >
        <Lineup
          background="#111111"
          ink="#FFFFFF"
          title={endTitle}
          subtitle={endSubtitle}
        />
      </Sequence>
    </AbsoluteFill>
  );
};

const LINEUP_HEIGHT = 620;

const Lineup: React.FC<{
  background: string;
  ink: string;
  title: string;
  subtitle: string;
}> = ({ background, ink, title, subtitle }) => {
  const frame = useCurrentFrame();
  const widths = LOOKS.map((l) => (l.width / l.height) * LINEUP_HEIGHT);

  return (
    <AbsoluteFill style={{ backgroundColor: background, color: ink }}>
      <div
        style={{
          position: "absolute",
          top: 210,
          width: "100%",
          textAlign: "center",
          fontFamily: FONTS.wide,
          fontWeight: 900,
          fontSize: 118,
          lineHeight: 1.02,
          letterSpacing: -2,
          whiteSpace: "pre-line",
          scale: interpolate(frame, [0, 8], [1.12, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: EASE_OUT,
          }),
        }}
      >
        {title}
      </div>
      <div
        style={{
          position: "absolute",
          top: 610,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          alignItems: "flex-end",
          gap: 4,
        }}
      >
        {LOOKS.map((look, i) => (
          <div
            key={look.src}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 26,
            }}
          >
            <Img
              src={look.src}
              style={{
                height: LINEUP_HEIGHT,
                width: widths[i],
                translate: interpolate(
                  frame,
                  [i * 2, i * 2 + 10],
                  ["0px 40px", "0px 0px"],
                  {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: EASE_OUT,
                  },
                ),
              }}
            />
            <div
              style={{
                width: 72,
                height: 72,
                borderRadius: 36,
                backgroundColor: ink,
                color: background,
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                fontFamily: FONTS.wide,
                fontWeight: 800,
                fontSize: 34,
                scale: interpolate(frame, [6 + i * 3, 14 + i * 3], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: POP,
                }),
              }}
            >
              {i + 1}
            </div>
          </div>
        ))}
      </div>
      <div
        style={{
          position: "absolute",
          top: 1360,
          width: "100%",
          textAlign: "center",
          fontFamily: FONTS.serif,
          fontStyle: "italic",
          fontSize: 92,
          opacity: interpolate(frame, [10, 18], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          translate: interpolate(frame, [10, 20], ["0px 24px", "0px 0px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: EASE_OUT,
          }),
        }}
      >
        {subtitle}
      </div>
    </AbsoluteFill>
  );
};

const FIGURE_HEIGHT = 1300;
const FIGURE_TOP = 360;
const FIGURE_CENTER_X = 500;

const LookScene: React.FC<{ look: Look; index: number }> = ({
  look,
  index,
}) => {
  const frame = useCurrentFrame();
  const figureWidth = (look.width / look.height) * FIGURE_HEIGHT;
  const figureLeft = FIGURE_CENTER_X - figureWidth / 2;
  const number = String(index + 1).padStart(2, "0");

  return (
    <AbsoluteFill style={{ backgroundColor: look.color }}>
      <div
        style={{
          position: "absolute",
          top: 520,
          right: 30,
          fontFamily: FONTS.wide,
          fontWeight: 900,
          fontSize: 720,
          lineHeight: 1,
          color: "rgba(255, 255, 255, 0.6)",
          translate: interpolate(frame, [0, 10], ["0px 90px", "0px 0px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: EASE_OUT,
          }),
        }}
      >
        {index + 1}
      </div>
      <div
        style={{
          position: "absolute",
          left: figureLeft + figureWidth * 0.1,
          top: FIGURE_TOP + FIGURE_HEIGHT - 34,
          width: figureWidth * 0.8,
          height: 60,
          borderRadius: "50%",
          background:
            "radial-gradient(closest-side, rgba(0,0,0,0.28), rgba(0,0,0,0))",
        }}
      />
      <Img
        src={look.src}
        style={{
          position: "absolute",
          left: figureLeft,
          top: FIGURE_TOP,
          width: figureWidth,
          height: FIGURE_HEIGHT,
          transformOrigin: "50% 100%",
          translate: interpolate(frame, [0, 9], ["0px 50px", "0px 0px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: EASE_OUT,
          }),
          scale: interpolate(frame, [0, 9], [1.05, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: EASE_OUT,
          }),
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 60,
          top: 170,
          color: "#111111",
        }}
      >
        <div
          style={{
            fontFamily: FONTS.wide,
            fontWeight: 500,
            fontSize: 30,
            letterSpacing: 4,
          }}
        >
          LOOK {number}/{String(LOOKS.length).padStart(2, "0")}
        </div>
        <div
          style={{
            fontFamily: FONTS.serif,
            fontStyle: "italic",
            fontSize: 84,
            lineHeight: 1.1,
            marginTop: 6,
            opacity: interpolate(frame, [3, 9], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {look.name}
        </div>
      </div>
      {look.tags.map((tag, k) => {
        const anchorX = figureLeft + tag.x * figureWidth;
        const anchorY = FIGURE_TOP + tag.y * FIGURE_HEIGHT;
        const onLeft = tag.x < 0.5;
        const start = 8 + k * 4;
        const progress = interpolate(frame, [start, start + 7], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: POP,
        });
        return (
          <div
            key={tag.label}
            style={{
              position: "absolute",
              top: anchorY - 22,
              height: 44,
              display: "flex",
              alignItems: "center",
              flexDirection: onLeft ? "row-reverse" : "row",
              ...(onLeft
                ? { right: 1080 - anchorX - 9 }
                : { left: anchorX - 9 }),
            }}
          >
            <div
              style={{
                width: 18,
                height: 18,
                borderRadius: 9,
                backgroundColor: "#FFFFFF",
                border: "4px solid #111111",
                boxSizing: "border-box",
                scale: progress,
              }}
            />
            <div
              style={{
                width: 40,
                height: 3,
                backgroundColor: "#111111",
                scale: `${progress} 1`,
                transformOrigin: onLeft ? "100% 50%" : "0% 50%",
              }}
            />
            <div
              style={{
                backgroundColor: "#FFFFFF",
                color: "#111111",
                borderRadius: 999,
                padding: "10px 18px",
                fontFamily: FONTS.sans,
                fontWeight: 600,
                fontSize: 30,
                whiteSpace: "nowrap",
                boxShadow: "0 6px 18px rgba(0,0,0,0.12)",
                scale: progress,
                transformOrigin: onLeft ? "100% 50%" : "0% 50%",
              }}
            >
              {tag.label}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
