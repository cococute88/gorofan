import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AI Creative Workspace",
  description: "나만의 로판AI + 하트픽션 — AI 캐릭터 채팅 & 소설 창작 워크스페이스",
  manifest: "/manifest.json",
  applicationName: "AI Creative Workspace",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "AICW",
  },
  icons: {
    icon: "/icons/icon-192.png",
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#7c3aed",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
