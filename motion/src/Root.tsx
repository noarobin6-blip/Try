import { Composition } from "remotion";
import "./fonts";
import { Defile } from "./videos/Defile";

// Même format que la vidéo de référence : 4:3, 30 i/s.
// 291 images = deux tours complets de la bande à la vitesse mesurée : boucle parfaite.
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Defile"
      component={Defile}
      durationInFrames={291}
      fps={30}
      width={1440}
      height={1080}
    />
  );
};
