// Service worker that adds the cross-origin isolation headers a static host cannot send,
// so the page may use SharedArrayBuffer (wasm threads). Registered by index.html when the
// page is not isolated; the page reloads once the worker controls it.
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", function (e) {
  if (e.request.cache === "only-if-cached" && e.request.mode !== "same-origin") return;
  e.respondWith(fetch(e.request).then(function (r) {
    if (r.status === 0) return r;
    var h = new Headers(r.headers);
    h.set("Cross-Origin-Embedder-Policy", "require-corp");
    h.set("Cross-Origin-Opener-Policy", "same-origin");
    return new Response(r.body, { status: r.status, statusText: r.statusText, headers: h });
  }));
});
