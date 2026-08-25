import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/schools/fl-fort-lauderdale-st-thomas-aquinas",
        destination: "/schools/fl-fort-lauderdale-saint-thomas-aquinas",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
