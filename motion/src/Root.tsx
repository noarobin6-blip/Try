import { Composition } from "remotion";
import { Defile, durationFor } from "./videos/Defile";

// Même format que la vidéo de référence : 4:3, 30 i/s.
// Durée = deux tours complets de la bande à la vitesse mesurée : boucle parfaite.
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Defile"
      component={Defile}
      durationInFrames={durationFor(1080)}
      fps={30}
      width={1440}
      height={1080}
    />
  );
};
