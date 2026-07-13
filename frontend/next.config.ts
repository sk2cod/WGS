import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // @vercel/og ships a compiled native module that Vercel's serverless file
  // tracer sometimes fails to include in the deployed bundle (surfaces in
  // production as "Cannot find module .../compiled/@vercel/og/index.node.js").
  // Marking it external skips bundling/tracing and resolves it from
  // node_modules at runtime instead, where it's actually present.
  serverExternalPackages: ["@vercel/og"],
};

export default nextConfig;
