/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  headers() {
    return [
      {
        source: "/activate/:token",
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      },
    ];
  },
};

export default nextConfig;
