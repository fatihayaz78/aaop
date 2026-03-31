import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import GlobalSearch from "@/components/global-search";
import { AuthProvider } from "@/contexts/AuthContext";

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
    <html lang="en" className="dark">
      <body className="min-h-screen" style={{ backgroundColor: "var(--background)" }}>
        <script dangerouslySetInnerHTML={{ __html: `
          (function(){var t=localStorage.getItem('captain-logar-theme')||'dark';
          document.documentElement.setAttribute('data-theme',t);
          document.documentElement.classList.toggle('dark',t==='dark');})();
        `}} />
        <AuthProvider>
          <Sidebar />
          <div className="transition-all md:ml-[var(--sidebar-width)]">
            <Header />
            <main className="p-4 md:p-6">{children}</main>
          </div>
          <GlobalSearch />
        </AuthProvider>
      </body>
    </html>
  );
}
