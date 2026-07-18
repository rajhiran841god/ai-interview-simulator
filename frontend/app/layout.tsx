import "./globals.css";

export const metadata = {
  title: "AI Interview Simulator — Pilot",
  description: "Practice MBA placement interviews with adaptive AI.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
