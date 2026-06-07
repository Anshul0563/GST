import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Create Account",
  robots: {
    index: false,
    follow: false,
  },
};

export default function RegisterLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
