"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

const MARKETING_ROUTES = [
  "/about",
  "/api-docs",
  "/apply",
  "/blog",
  "/changelog",
  "/contact",
  "/docs",
  "/features",
  "/pricing",
  "/privacy",
  "/security",
  "/terms",
  "/use-cases",
];

export function RootShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Chat page renders its own Sidebar inside its own 3-column grid.
  const isChat = pathname === "/chat" || pathname.startsWith("/chat/");
  // Landing, login, share, and marketing/legal pages render without sidebar chrome.
  const isLogin = pathname === "/login";
  const isLanding = pathname === "/";
  const isShare = pathname.startsWith("/share");
  const isMarketing = MARKETING_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );

  if (isLogin || isLanding || isShare || isMarketing) return <>{children}</>;
  if (isChat) return <>{children}</>;

  return (
    <>
      <Sidebar />
      <div className="main-content">{children}</div>
    </>
  );
}
