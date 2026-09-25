import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "منصة APEX — مكتب التداول الآلي",
  description:
    "منصة تداول احترافية آلية: محرك VWAP · OBV · MACD · RSI مع كشف الانضغاط والاختراق، التعرف على النماذج السعرية، وخطط تداول مولّدة آليًا.",
};

export const viewport: Viewport = {
  themeColor: "#0B0F17",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl" className="dark">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
