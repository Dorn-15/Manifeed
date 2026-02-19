import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AdminNavbar } from "@/features/navigation/components/AdminNavbar";

import "./globals.css";

export const metadata: Metadata = {
  title: "Manifeed Admin",
  description: "Manifeed RSS administration",
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>
        <AdminNavbar />
        {children}
      </body>
    </html>
  );
}
