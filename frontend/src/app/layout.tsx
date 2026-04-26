import "./globals.css";
import { RootShell } from "@/components/ui/RootShell";
import { AuthProvider } from "@/components/AuthProvider";
import { LocaleProvider } from "@/lib/locale";

export const metadata = {
  title: "BD Go",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <LocaleProvider>
          <AuthProvider>
            <RootShell>{children}</RootShell>
          </AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
