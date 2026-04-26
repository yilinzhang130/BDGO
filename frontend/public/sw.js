/**
 * BD Go Service Worker  (P3-13)
 *
 * Caching strategy:
 *   - App shell (HTML navigation): network-first, fallback to /offline
 *   - Static assets (/_next/static/**): cache-first (immutable by hash)
 *   - /api/reports/history: network-first, cache fallback (offline report viewing)
 *   - Other /api/*: network-only (live data, no caching)
 *   - Everything else: network-first
 */

const CACHE_VERSION = "bdgo-v1";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const REPORTS_CACHE = `${CACHE_VERSION}-reports`;

// App shell pages to pre-cache on install
const APP_SHELL = ["/", "/chat", "/reports", "/offline"];

// ─── Install ──────────────────────────────────────────────────────────────────

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(APP_SHELL).catch(() => {}))
      .then(() => self.skipWaiting()),
  );
});

// ─── Activate ────────────────────────────────────────────────────────────────

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => !k.startsWith(CACHE_VERSION))
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// ─── Fetch ────────────────────────────────────────────────────────────────────

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin GET requests
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // ── Next.js static assets: cache-first (filenames include content hash) ──
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(cacheFirst(STATIC_CACHE, request));
    return;
  }

  // ── Report history: network-first with offline fallback ──
  if (url.pathname === "/api/reports/history") {
    event.respondWith(networkFirstWithCache(REPORTS_CACHE, request));
    return;
  }

  // ── Other API calls: network-only ──
  if (url.pathname.startsWith("/api/")) return;

  // ── Navigation (HTML pages): network-first with offline fallback ──
  if (request.mode === "navigate") {
    event.respondWith(navigationHandler(request));
    return;
  }

  // ── Icons, manifest, other public assets: network-first ──
  event.respondWith(networkFirst(STATIC_CACHE, request));
});

// ─── Strategy helpers ────────────────────────────────────────────────────────

async function cacheFirst(cacheName, request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response("Asset unavailable offline", { status: 503 });
  }
}

async function networkFirst(cacheName, request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached ?? new Response("Unavailable offline", { status: 503 });
  }
}

async function networkFirstWithCache(cacheName, request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request, { cacheName });
    if (cached) return cached;
    // Return empty reports list so the UI renders gracefully offline
    return new Response(JSON.stringify({ reports: [], offline: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function navigationHandler(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch {
    // Try the exact path first, then fall back to /offline
    const cached = await caches.match(request);
    if (cached) return cached;
    const offline = await caches.match("/offline");
    return (
      offline ??
      new Response(
        `<!DOCTYPE html><html><body style="font-family:sans-serif;padding:2rem;text-align:center">
        <h2>You are offline</h2><p>Open BD Go once you have an internet connection.</p>
        </body></html>`,
        { headers: { "Content-Type": "text/html" } },
      )
    );
  }
}
