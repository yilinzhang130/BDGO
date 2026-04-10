"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

export function RootShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Chat page renders its own Sidebar inside its own 3-column grid.
  const isChat = pathname === "/chat" || pathname.startsWith("/chat/");
  // Login page renders without sidebar chrome.
  const isLogin = pathname === "/login";

  if (isLogin) return <>{children}</>;
  if (isChat) return <>{children}</>;

  return (
    <>
      <Sidebar />
      <div className="main-content">{children}</div>
    </>
  );
}
