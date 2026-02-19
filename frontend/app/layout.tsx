import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Lora, DM_Sans } from "next/font/google";
import "./globals.css";
import { Auth0Provider } from "@/components/Auth0Provider";
import { LayoutShell } from "@/components/LayoutShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const lora = Lora({
  variable: "--font-lora",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "NoShot (You're Still LeetCoding)",
  description:
    "The competitive platform that benchmarks and gamifies your ability to prompt AI to write code. Monkeytype for the AI era.",
  icons: {
    icon: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${lora.variable} ${dmSans.variable} antialiased`}
      >
        <Auth0Provider>
          <LayoutShell>{children}</LayoutShell>
        </Auth0Provider>
      </body>
    </html>
  );
}
