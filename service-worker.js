const CACHE_NAME = 'reshatel-v1.0-equation-input-fix2';
const CACHE_PREFIX = 'reshatel-';
const PYODIDE_PREFIX = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';
const APP_FILES = [
  './', './index.html', './styles.css?v=9', './app.js?v=11', './solver.py',
  './manifest.webmanifest', './icon.svg', './icon-180.png',
  './icon-192.png', './icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(APP_FILES);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const oldCaches = (await caches.keys()).filter(
      key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME
    );
    await Promise.all(oldCaches.map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  const isPyodide = url.href.startsWith(PYODIDE_PREFIX);
  const isLocal = url.origin === self.location.origin;
  if (!isPyodide && !isLocal) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;

    try {
      const response = await fetch(request);
      if (response && (response.ok || response.type === 'opaque')) {
        try {
          await cache.put(request, response.clone());
        } catch (error) {
          // Кэш может быть переполнен или ограничен браузером.
          console.warn('Не удалось сохранить ресурс для офлайн-режима:', request.url, error);
        }
      }
      return response;
    } catch (error) {
      const fallback = await cache.match(request);
      if (fallback) return fallback;
      throw error;
    }
  })());
});
