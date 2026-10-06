import { CalculateMetadataFunction, Composition } from "remotion";
import { SmokeTest } from "./SmokeTest";

type Props = {};

const calculateMetadata: CalculateMetadataFunction<Props> = () => {
  return {};
};

export const MyComposition = () => {
  return (
    <Composition
      id="SmokeTest"
      component={SmokeTest}
      durationInFrames={90}
      fps={30}
      width={1920}
      height={1080}
      calculateMetadata={calculateMetadata}
    />
  );
};
