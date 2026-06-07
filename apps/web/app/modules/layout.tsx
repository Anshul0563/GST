import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Workspace Modules",
  robots: {
    index: false,
    follow: false,
  },
};

export default function ModulesLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
