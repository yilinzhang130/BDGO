import "./globals.css";
import { RootShell } from "@/components/ui/RootShell";
import { AuthProvider } from "@/components/AuthProvider";

export const metadata = {
  title: "BD Go",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <AuthProvider>
          <RootShell>{children}</RootShell>
        </AuthProvider>
      </body>
    </html>
  );
}
