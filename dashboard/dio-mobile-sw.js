const SHELL_CACHE = "dio-mobile-shell-v1";
const SHELL_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/dio-mobile-icon-192.png",
  "/dio-mobile-icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then(cache => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== SHELL_CACHE).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

function networkOnlyTruth(request) {
  return fetch(request, { cache: "no-store" });
}

async function shellWithOfflineFallback(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const copy = response.clone();
      caches.open(SHELL_CACHE).then(cache => cache.put(request, copy));
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return caches.match("/");
  }
}

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname === "/api/launcher/state" || url.pathname.startsWith("/api/")) {
    event.respondWith(networkOnlyTruth(request));
    return;
  }

  event.respondWith(shellWithOfflineFallback(request));
});
