import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Mini DNS Resolver — Web companion",
  description:
    "Friendly web companion for the Mini DNS Resolver project: look up domains, learn caching and DNS-over-HTTPS, and run the full UDP resolver locally.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-zinc-950 text-zinc-100 antialiased`}>
        <SiteNav />
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-5xl border-t border-zinc-800 px-4 py-6 text-center text-xs text-zinc-500">
          This site uses DNS-over-HTTPS from Vercel — it is not the same as running the Python UDP stub on your laptop.
        </footer>
      </body>
    </html>
  );
}
