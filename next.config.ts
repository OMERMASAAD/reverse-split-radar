import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["*.e2b.app"],
  /** تصدير ثابت كامل — يُخزَّن في site/ ويُقدَّم بخادم ملفات بسيط resilient */
  output: "export",
  images: { unoptimized: true },
  /** بناء GitHub Pages يحتاج بادئة مسار المشروع */
  ...(process.env.PAGES_BUILD
    ? { basePath: "/reverse-split-radar", assetPrefix: "/reverse-split-radar" }
    : {}),
  /** بناء محمول بمسارات نسبية — يعمل عبر CDN (jsDelivr) أو أي مضيف */
  ...(process.env.RELATIVE_BUILD ? { assetPrefix: "./" } : {}),
};

export default nextConfig;
