import "./globals.css";
import { RootShell } from "@/components/ui/RootShell";
import { AuthProvider } from "@/components/AuthProvider";
import { LocaleProvider } from "@/lib/locale";
import { ServiceWorkerRegistration } from "@/components/ui/ServiceWorkerRegistration";
import { OfflineIndicator } from "@/components/ui/OfflineIndicator";

export const metadata = {
  title: "BD Go",
  description: "Biotech BD Intelligence Platform",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "BD Go",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#1E3A8A",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <head>
        <link rel="apple-touch-icon" href="/icons/icon.svg" />
      </head>
      <body>
        <ServiceWorkerRegistration />
        <OfflineIndicator />
        <LocaleProvider>
          <AuthProvider>
            <RootShell>{children}</RootShell>
          </AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
