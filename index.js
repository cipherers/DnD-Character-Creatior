export default {
  async fetch(request, env, ctx) {
    const RENDER_ORIGIN = "https://dnd-character-creatior.onrender.com";
    const ALLOWED_ORIGIN = "https://cipherers.github.io";

    const url = new URL(request.url);
    const path = url.pathname;

    // --- CORS preflight ---
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request, ALLOWED_ORIGIN) });
    }

    // --- EDGE RATE LIMIT (before hitting Render) ---
    // Identify caller by IP (Cloudflare provides this)
    const ip = request.headers.get("CF-Connecting-IP") || "0.0.0.0";

    const rule = rateLimitRule(request.method, path);
    if (rule) {
      const id = env.RATE_LIMITER.idFromName(`${ip}:${rule.key}`);
      const stub = env.RATE_LIMITER.get(id);

      const rlResp = await stub.fetch("https://rate.limit/check", {
        method: "POST",
        body: JSON.stringify({ limit: rule.limit, windowSec: rule.windowSec }),
      });

      if (rlResp.status === 429) {
        const headers = new Headers(corsHeaders(request, ALLOWED_ORIGIN));
        headers.set("Content-Type", "application/json");
        return new Response(JSON.stringify({ error: "Rate limit exceeded. Try again later." }), {
          status: 429,
          headers,
        });
      }
    }

    // --- EDGE CACHE (only safe public GET endpoints) ---
    const cacheable = isCacheableGET(request.method, path);
    if (cacheable) {
      const cacheKey = new Request(url.toString(), request);
      const cache = caches.default;
      const cached = await cache.match(cacheKey);
      if (cached) return withCors(cached, request, ALLOWED_ORIGIN);
      // if not cached, fall through to fetch and store
      const resp = await proxyToRender(request, RENDER_ORIGIN, env);
      const respToCache = new Response(resp.body, resp);

      // Cache for 1 hour (tune if you want)
      respToCache.headers.set("Cache-Control", "public, max-age=3600");

      ctx.waitUntil(cache.put(cacheKey, respToCache.clone()));
      return withCors(respToCache, request, ALLOWED_ORIGIN);
    }

    // --- Normal proxy (no caching) ---
    const resp = await proxyToRender(request, RENDER_ORIGIN);
    return withCors(resp, request, ALLOWED_ORIGIN);
  },
};

// ------------------- Durable Object -------------------
export class RateLimiter {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    const { limit, windowSec } = await request.json();

    const now = Date.now();
    const key = "bucket";
    const bucket = (await this.state.storage.get(key)) || { count: 0, resetAt: now + windowSec * 1000 };

    // reset window
    if (now > bucket.resetAt) {
      bucket.count = 0;
      bucket.resetAt = now + windowSec * 1000;
    }

    bucket.count += 1;
    await this.state.storage.put(key, bucket);

    if (bucket.count > limit) return new Response("rate_limited", { status: 429 });
    return new Response("ok", { status: 200 });
  }
}

// ------------------- Helpers -------------------
function corsHeaders(request, allowedOrigin) {
  const origin = request.headers.get("Origin");
  const allowOrigin = origin === allowedOrigin ? origin : allowedOrigin;

  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": request.headers.get("Access-Control-Request-Headers") || "*",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function withCors(resp, request, allowedOrigin) {
  const headers = new Headers(resp.headers);
  const cors = corsHeaders(request, allowedOrigin);
  for (const [k, v] of Object.entries(cors)) headers.set(k, v);
  return new Response(resp.body, { status: resp.status, headers });
}

async function proxyToRender(request, renderOrigin, env) {
  const url = new URL(request.url);
  const targetUrl = renderOrigin + url.pathname + url.search;

  const headers = new Headers(request.headers);

  if (env?.PROXY_SECRET) {
    headers.set("X-Proxy-Secret", env.PROXY_SECRET);
  }

  headers.delete("host");

  const init = {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
    redirect: "manual",
  };

  return fetch(targetUrl, init);
}

function isCacheableGET(method, path) {
  if (method !== "GET") return false;

  // Only cache these specific endpoints
  if (path === "/get-races") return true;
  if (path === "/get-classes") return true;
  if (path === "/get-backgrounds") return true;
  if (path === "/get-all-equipment") return true;
  if (path === "/get-feats") return true;

  // cache class details
  if (path.startsWith("/get-class-details/")) return true;

  // optional: spells can be cached but query-string varies; still ok
  if (path === "/get-spells") return true;

  return false;
}

function rateLimitRule(method, path) {
  // Return { key, limit, windowSec } or null

  // Auth / account endpoints
  if (method === "POST" && path === "/login") return { key: "login", limit: 10, windowSec: 60 };

  // High-cost writes
  if (method === "POST" && path === "/create-character") return { key: "create_character", limit: 30, windowSec: 3600 };
  if (method === "POST" && path === "/add-dnd-info") return { key: "add_dnd_info", limit: 30, windowSec: 3600 };
  if (method === "POST" && path === "/upload-portrait") return { key: "upload_portrait", limit: 10, windowSec: 3600 };

  // Updates
  if (method === "POST" && path === "/update-character") return { key: "update_character", limit: 60, windowSec: 3600 };
  if (method === "POST" && path === "/update-character-currency") return { key: "update_currency", limit: 120, windowSec: 3600 };
  if (method === "POST" && (path === "/add-inventory-item" || path === "/remove-inventory-item")) {
    return { key: "inventory", limit: 120, windowSec: 3600 };
  }

  // Deletes
  if (method === "DELETE" && path.startsWith("/api/delete-character/")) {
    return { key: "delete_character", limit: 60, windowSec: 3600 };
  }

  // Optional: protect check-auth from spam
  if (method === "GET" && path === "/api/check-auth") return { key: "check_auth", limit: 120, windowSec: 60 };

  return null;
}
