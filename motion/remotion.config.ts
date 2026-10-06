/**
 * Note: When using the Node.JS APIs, the config file
 * doesn't apply. Instead, pass options directly to the APIs.
 *
 * All configuration options: https://remotion.dev/docs/config
 */

import fs from "node:fs";
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);

// Rendu de qualité : JPEG haute qualité, H.264 avec CRF bas, pixel format compatible partout.
Config.setJpegQuality(95);
Config.setCodec("h264");
Config.setCrf(16);
Config.setPixelFormat("yuv420p");
Config.setColorSpace("bt709");
Config.setChromiumOpenGlRenderer("angle");

// Dans les sessions cloud, le téléchargement de Chrome par Remotion est bloqué :
// on réutilise le headless shell préinstallé par Playwright s'il existe.
// Sur une machine normale, ce chemin n'existe pas et Remotion télécharge le sien.
const PLAYWRIGHT_HEADLESS_SHELL =
  "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
if (fs.existsSync(PLAYWRIGHT_HEADLESS_SHELL)) {
  Config.setBrowserExecutable(PLAYWRIGHT_HEADLESS_SHELL);
}
