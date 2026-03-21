import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";

export const metadata: Metadata = {
  title: "Captain logAR — AAOP",
  description: "AI-powered OTT platform operations",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen" style={{ backgroundColor: "var(--background)" }}>
        <Sidebar />
        <div style={{ marginLeft: "var(--sidebar-width)" }}>
          <Header />
          <main className="p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
