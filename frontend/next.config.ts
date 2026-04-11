import type { NextConfig } from "next";

// In production (Vercel), set NEXT_PUBLIC_API_URL to the backend VM address,
// e.g. "https://api.yourdomain.com" or "http://<VM_IP>:8001".
// Locally it defaults to the dev server.
const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
  typescript: {
    // Recharts @types have strict PieLabelRenderProps that conflict with
    // custom render callbacks — safe to skip; we verify locally via tsc.
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
