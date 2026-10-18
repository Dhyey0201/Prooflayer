import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The repo keeps AGENTS.md local and uncommitted by convention; don't let
  // Next regenerate one at the app root on every dev/build run.
  agentRules: false,
  turbopack: {
    // Pin the workspace root to this app; otherwise Turbopack walks up to the
    // nearest lockfile, which on some machines sits outside the git repo.
    root: path.join(__dirname),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
