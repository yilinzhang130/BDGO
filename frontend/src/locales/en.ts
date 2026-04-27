/**
 * English UI strings.
 * Keys mirror zh.ts exactly. Any key missing here falls back to zh.ts.
 */
export const en: Record<string, string> = {
  // ── Sidebar ──────────────────────────────────────────────
  "nav.search": "Search…",
  "nav.newChat": "New Chat",
  "nav.recent": "Recent",
  "nav.database": "Database",
  "nav.news": "News",
  "nav.tools": "Tools",
  "nav.admin": "Admin",

  // Nav item labels
  "nav.companies": "Companies",
  "nav.assets": "Assets",
  "nav.clinical": "Clinical",
  "nav.ip": "Patents",
  "nav.buyers": "Buyers",
  "nav.deals": "Deals",
  "nav.dashboard": "Dashboard",
  "nav.sell": "Sell-side",
  "nav.watchlist": "Watchlist",
  "nav.outreach": "Outreach",
  "nav.catalysts": "Catalysts",
  "nav.reports": "Reports",
  "nav.conference": "Conferences",
  "nav.manage": "Manage",
  "nav.team": "Team",
  "nav.notifications": "Notifications",

  // Sidebar footer
  "nav.defaultUser": "User",
  "nav.defaultRole": "BD Professional",
  "nav.logoutLabel": "Sign out",
  "nav.logoutTitle": "Sign out",
  "nav.tagline": "Biopharma BD Intelligence",

  // AIDD button
  "nav.projectCenter": "Project Center (AIDD)",
  "nav.projectCenterLoading": "Redirecting…",
  "nav.projectCenterError": "Failed to generate redirect link, please try again",

  // Language toggle (shows what you'll switch TO)
  "nav.switchLang": "中",

  // ── Login page ───────────────────────────────────────────
  "login.tab.login": "Sign In",
  "login.tab.register": "Register",
  "login.label.name": "Name",
  "login.label.email": "Email",
  "login.label.password": "Password",
  "login.label.inviteCode": "Invite Code",
  "login.placeholder.name": "Your full name",
  "login.placeholder.email": "your@email.com",
  "login.placeholder.password.login": "Enter password",
  "login.placeholder.password.register": "At least 6 characters",
  "login.placeholder.inviteCode": "Enter invite code",
  "login.submit.login": "Sign In",
  "login.submit.register": "Create Account",
  "login.submit.loading": "Loading…",
  "login.switch.noAccount": "Don't have an account?",
  "login.switch.hasAccount": "Already have an account?",
  "login.switch.toRegister": "Sign up free",
  "login.switch.toLogin": "Sign in",
  "login.forgotPassword": "Forgot password?",

  // Login validation errors
  "login.error.invalidEmail": "Please enter a valid email address",
  "login.error.passwordTooShort": "Password must be at least 6 characters",
  "login.error.nameRequired": "Please enter your name",
  "login.error.inviteRequired": "Please enter an invite code",
  "login.error.fallback": "Something went wrong, please try again",

  // ── Auth errors (AuthProvider) ───────────────────────────
  "auth.error.wrongPassword": "Incorrect email or password, please try again",
  "auth.error.authFailed": "Authentication failed",
  "auth.error.noPermission": "Access denied",
  "auth.error.emailNotFound": "Email not found — please register first",
  "auth.error.apiNotFound": "Endpoint not found",
  "auth.error.emailExists": "Email already registered",
  "auth.error.badRequest": "Invalid request format",
  "auth.error.incomplete": "Please fill in all required fields",
  "auth.error.tooManyRequests": "Too many requests — please wait and try again",
  "auth.error.serverError": "Service temporarily unavailable (server error)",
  "auth.error.networkError": "Cannot connect to server — check your network",
  "auth.error.fallback": "Something went wrong, please try again",
};
