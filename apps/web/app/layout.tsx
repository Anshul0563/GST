import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GST Bharat",
  description: "eCommerce GST automation for Indian sellers"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

