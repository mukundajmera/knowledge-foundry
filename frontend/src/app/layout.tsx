import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Knowledge Foundry",
  description: "Enterprise AI Knowledge Management Platform — Ask questions, get cited answers.",
  keywords: ["knowledge management", "AI", "RAG", "enterprise search"],
  authors: [{ name: "Knowledge Foundry Team" }],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="color-scheme" content="dark" />
      </head>
      <body>{children}</body>
    </html>
  );
}
