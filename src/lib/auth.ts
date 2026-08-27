/**
 * Session auth for the site-wide login gate.
 *
 * Edge-compatible on purpose: src/proxy.ts runs in the Edge runtime, so this
 * uses Web Crypto (HMAC-SHA256) rather than node:crypto.
 *
 * The cookie holds a signed payload, not just a flag — an unsigned "logged in"
 * cookie could simply be set by hand in devtools to walk past the gate.
 *
 * Credentials and signing secret come from env when set; the fallbacks below
 * are committed to git and are therefore NOT secret. Set SITE_AUTH_USER /
 * SITE_AUTH_PASSWORD / SITE_AUTH_SECRET before deploying anywhere public.
 */
const FALLBACK_USER = "fridayradar";
const FALLBACK_PASSWORD = "friday-night-lights";
const FALLBACK_SECRET = "fridayradar-dev-signing-key-change-me";

const EXPECTED_USER = process.env.SITE_AUTH_USER || FALLBACK_USER;
const EXPECTED_PASSWORD = process.env.SITE_AUTH_PASSWORD || FALLBACK_PASSWORD;
const SECRET = process.env.SITE_AUTH_SECRET || FALLBACK_SECRET;

export const SESSION_COOKIE = "fr_session";
export const SESSION_TTL_MS = 12 * 60 * 60 * 1000; // 12 hours

const encoder = new TextEncoder();

/** Length-independent compare, so a wrong guess leaks nothing via timing. */
function safeEqual(a: string, b: string): boolean {
  const x = encoder.encode(a);
  const y = encoder.encode(b);
  let diff = x.length ^ y.length;
  const len = Math.max(x.length, y.length);
  for (let i = 0; i < len; i++) {
    diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  }
  return diff === 0;
}

/** Both fields are always compared — no early return on a bad username. */
export function credentialsValid(user: string, password: string): boolean {
  const okUser = safeEqual(user, EXPECTED_USER);
  const okPassword = safeEqual(password, EXPECTED_PASSWORD);
  return okUser && okPassword;
}

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Returns a plain-ArrayBuffer view so it satisfies Web Crypto's BufferSource. */
function fromBase64Url(value: string): Uint8Array<ArrayBuffer> {
  let s = value.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const binary = atob(s);
  const out = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

async function signingKey(): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

export async function createSessionToken(user: string = EXPECTED_USER): Promise<string> {
  const payload = encoder.encode(JSON.stringify({ u: user, exp: Date.now() + SESSION_TTL_MS }));
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", await signingKey(), payload));
  return `${toBase64Url(payload)}.${toBase64Url(sig)}`;
}

/** True only for a token this server signed that has not expired. */
export async function sessionTokenValid(token: string | undefined | null): Promise<boolean> {
  if (!token) return false;
  const dot = token.indexOf(".");
  if (dot < 1) return false;
  try {
    const payload = fromBase64Url(token.slice(0, dot));
    const sig = fromBase64Url(token.slice(dot + 1));
    const ok = await crypto.subtle.verify("HMAC", await signingKey(), sig, payload);
    if (!ok) return false;
    const data = JSON.parse(new TextDecoder().decode(payload)) as { exp?: unknown };
    return typeof data.exp === "number" && data.exp > Date.now();
  } catch {
    return false;
  }
}

/**
 * Only same-origin absolute paths may be redirected to after login.
 * Anything else (protocol-relative "//evil.com", absolute URLs) is dropped so
 * the ?next= param can't be used as an open redirect.
 */
export function safeNextPath(value: string | null | undefined): string {
  if (!value) return "/";
  if (!value.startsWith("/") || value.startsWith("//")) return "/";
  return value;
}
