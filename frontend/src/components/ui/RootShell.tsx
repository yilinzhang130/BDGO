"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

export function RootShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Chat page renders its own Sidebar inside its own 3-column grid.
  const isChat = pathname === "/chat" || pathname.startsWith("/chat/");
  // Landing and login pages render without sidebar chrome.
  const isLogin = pathname === "/login";
  const isLanding = pathname === "/";

  if (isLogin || isLanding) return <>{children}</>;
  if (isChat) return <>{children}</>;

  return (
    <>
      <Sidebar />
      <div className="main-content">{children}</div>
    </>
  );
}
