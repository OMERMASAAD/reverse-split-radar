import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["*.e2b.app"],
  /** تصدير ثابت كامل — يُخزَّن في site/ ويُقدَّم بخادم ملفات بسيط resilient */
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
