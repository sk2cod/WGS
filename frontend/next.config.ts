import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next's internal og/image-response module dynamically requires its own
  // compiled @vercel/og binary (next/dist/compiled/@vercel/og/index.node.js);
  // the file exists locally but Vercel's serverless file tracer misses it
  // since it's a dynamic, not statically-analyzable, require. Surfaces in
  // production as "Cannot find module .../compiled/@vercel/og/index.node.js"
  // on every /api/render call. Force it into the traced bundle explicitly.
  outputFileTracingIncludes: {
    "/api/render": ["./node_modules/next/dist/compiled/@vercel/og/**"],
  },
};

export default nextConfig;
