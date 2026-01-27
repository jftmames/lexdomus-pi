import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css"; // 👈 Importante: Aquí se cargan tus estilos "Glassmorphism"

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LexDomus-PI",
  description: "Inteligencia Artificial Jurídica",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
