import type { Metadata } from "next";
import "./globals.css";

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
      {/* Usamos font-sans de Tailwind (Arial/System) en lugar de descargar Inter */}
      <body className="font-sans antialiased bg-[var(--bg)] text-[var(--ink)]">
        {children}
      </body>
    </html>
  );
}
