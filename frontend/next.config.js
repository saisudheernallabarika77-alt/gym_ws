/** @type {import('next').NextConfig} */
// This rewrite runs server-side, inside the Next.js process itself (not in
// the browser), so 127.0.0.1 correctly means "the backend on this same
// machine" regardless of what host a teammate's browser used to reach the
// frontend over the LAN. Do not confuse this with lib/api.ts's BASE, which
// runs in the browser and must stay relative for the same reason in reverse.
const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

module.exports = {
  reactStrictMode: true,
  images: { remotePatterns: [{ protocol: "http", hostname: "127.0.0.1" },
                             { protocol: "http", hostname: "localhost" }] },
  async rewrites() {
    return [
      { source: "/api/:path*",     destination: `${API}/api/:path*` },
      { source: "/uploads/:path*", destination: `${API}/uploads/:path*` },
    ];
  },
};
