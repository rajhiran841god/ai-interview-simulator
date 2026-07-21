import "./globals.css";
import { Fraunces, Source_Sans_3, IBM_Plex_Mono } from "next/font/google";

// PlacementOS design system — see tailwind.config.ts and
// docs/PlacementOS_Design_System.md for the reasoning behind these
// specific choices.
const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-fraunces",
  display: "swap",
});

const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-source-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata = {
  title: "PlacementOS — Adaptive Interview Practice",
  description: "Practice MBA placement interviews with adaptive, evidence-grounded AI feedback.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${fraunces.variable} ${sourceSans.variable} ${plexMono.variable}`}>
      <body className="bg-paper text-ink font-sans">{children}</body>
    </html>
  );
}
