const SHELL_CACHE = "kerem-shell-v1";
const SHELL = [
  "/",
  "/dashboard",
  "/static/index.html",
  "/static/dashboard.html",
  "/static/privacy.html",
  "/static/terms.html",
  "/static/styles.css?v=20261125a",
  "/static/app.js?v=20261125a",
  "/static/admin.js?v=20261125a",
  "/static/manifest.json",
  "/static/icons/icon-192.svg",
  "/static/icons/icon-512.svg",
];

function isApiRequest(url) {
  return url.pathname.startsWith("/auth") ||
    url.pathname.startsWith("/appointments") ||
    url.pathname.startsWith("/admin") ||
    url.pathname.startsWith("/notifications") ||
    url.pathname.startsWith("/services") ||
    url.pathname.startsWith("/health");
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (isApiRequest(url)) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(JSON.stringify({ detail: "Sin conexión. Esta acción requiere internet." }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          if (cached) return cached;
          const path = url.pathname.startsWith("/dashboard") ? "/dashboard" : "/";
          return caches.match(path);
        })
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
