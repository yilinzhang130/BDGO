import "./globals.css";
import { RootShell } from "@/components/ui/RootShell";

export const metadata = {
  title: "BD Go",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <RootShell>{children}</RootShell>
      </body>
    </html>
  );
}
