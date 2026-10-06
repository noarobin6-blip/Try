import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FONTS } from "./fonts";


// Composition de vérification de la chaîne de rendu (polices, spring, interpolation).
// À remplacer par la vraie vidéo.
export const SmokeTest: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({ frame, fps, config: { damping: 200 } });
  const subtitle = interpolate(frame, [20, 45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: "radial-gradient(circle at 30% 20%, #1e293b, #020617)",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: FONTS.display,
        color: "white",
      }}
    >
      <div
        style={{
          fontSize: 140,
          fontWeight: 800,
          letterSpacing: -4,
          transform: `translateY(${(1 - enter) * 60}px)`,
          opacity: enter,
        }}
      >
        Motion prêt
      </div>
      <div
        style={{
          fontSize: 44,
          fontFamily: FONTS.serif,
          fontStyle: "italic",
          opacity: subtitle * 0.7,
          transform: `translateY(${(1 - subtitle) * 20}px)`,
          marginTop: 24,
        }}
      >
        Remotion · GSAP · Lottie
      </div>
    </AbsoluteFill>
  );
};
