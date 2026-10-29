/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  logging: {
    // Legacy path tokens are rejected by proxy.ts and must not reach development logs.
    incomingRequests: { ignore: [/^\/activate\/.+/] },
  },
  headers() {
    return [
      {
        source: "/activate",
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      },
    ];
  },
};

export default nextConfig;
