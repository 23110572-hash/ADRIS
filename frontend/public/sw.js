const CACHE = "adris-safety-v2";
const SAFETY_PATHS = new Set(["/emergency", "/reporting", "/offline"]);
const CORE = ["/emergency", "/reporting", "/offline", "/manifest.webmanifest", "/icons/adris-icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.allSettled(CORE.map((path) => cache.add(new Request(path, { cache: "reload" })))),
    ),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (SAFETY_PATHS.has(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const update = fetch(event.request).then((response) => {
          if (response.ok) event.waitUntil(caches.open(CACHE).then((cache) => cache.put(event.request, response.clone())));
          return response;
        });
        return cached || update.catch(() => caches.match("/offline"));
      }),
    );
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match("/offline")));
  }
});
