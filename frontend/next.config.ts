import type { NextConfig } from "next";

/**
 * Next.js configuration for the Tactiqo web application.
 *
 * @remarks
 * Team crests, competition logos and country flags are not project assets: the
 * provider serves them from its own CDN and the backend passes the absolute URL
 * through as part of the product contract. `next/image` refuses to optimize an
 * image whose host is not declared here and fails the request instead, so the
 * host has to be allowed explicitly for a crest to render at all.
 *
 * The pattern is deliberately narrow. It names one protocol and one host, so a
 * URL that ever arrives pointing somewhere else is rejected rather than proxied
 * by the application's own image optimizer.
 */
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.sportmonks.com",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
