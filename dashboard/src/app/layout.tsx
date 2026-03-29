import type { Metadata } from "next";
import { Nav } from "@/components/nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "GDS Agent Dashboard",
  description: "Multi-Agent Pipeline monitoring and management",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW">
      <body>
        <Nav />
        <main className="ml-56 p-6 min-h-screen">{children}</main>
      </body>
    </html>
  );
}
