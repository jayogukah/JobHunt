import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// GitHub Pages serves this repo at https://<user>.github.io/JobHunt/.
// Paths are case-sensitive, so "JobHunt" (capital J, capital H) must match
// the repo name exactly. Change this if you rename the repo.
export default defineConfig({
  base: "/JobHunt/",
  build: {
    outDir: "../docs",
    emptyOutDir: true,
  },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/icon-192.png", "icons/icon-512.png"],
      workbox: {
        cacheId: "jobhunt-v1",
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/raw\.githubusercontent\.com\/.*\/(jobs|meta)\.json$/,
            handler: "NetworkFirst",
            options: {
              cacheName: "jobhunt-data",
              networkTimeoutSeconds: 8,
              expiration: { maxEntries: 8, maxAgeSeconds: 60 * 60 * 24 * 14 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      manifest: {
        name: "JobHunt",
        short_name: "JobHunt",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "/JobHunt/",
        scope: "/JobHunt/",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
    }),
  ],
});
