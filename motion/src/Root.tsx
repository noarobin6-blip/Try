import { Composition, Folder } from "remotion";
import "./fonts";
import { Carousel } from "./videos/Carousel";
import { Marquee } from "./videos/Marquee";
import { OutfitCheck } from "./videos/OutfitCheck";

// Format vertical 9:16 (1080×1920) pour Reels et TikTok.
export const RemotionRoot: React.FC = () => {
  return (
    <Folder name="Tenues">
      <Composition
        id="P1-Defile"
        component={Marquee}
        durationInFrames={600}
        fps={60}
        width={1080}
        height={1920}
        defaultProps={{
          figureHeight: 1680,
          top: 0,
          gap: 0,
          kicker: "NOUVEAU DROP",
          title: "Y2K EDIT",
          subtitle: "DISPO EN LIGNE",
          textCenterY: 640,
        }}
      />
      <Composition
        id="P2-LequelTuPrends"
        component={OutfitCheck}
        durationInFrames={330}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          hookTitle: "5 LOOKS\nY2K",
          hookQuestion: "lequel tu prends ?",
          endTitle: "COMMENTE\nTON NUMÉRO",
          endSubtitle: "dispo en ligne",
        }}
      />
      <Composition
        id="P3-Carrousel"
        component={Carousel}
        durationInFrames={480}
        fps={60}
        width={1080}
        height={1920}
        defaultProps={{
          title: "Y2K",
          titleAccent: "edit",
          kicker: "05 LOOKS · PIÈCES UNIQUES",
        }}
      />
    </Folder>
  );
};
