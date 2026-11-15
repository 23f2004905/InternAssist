const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const localBaseUrl = typeof window === "undefined"
  ? "http://localhost:5001/api"
  : `${window.location.protocol}//${window.location.hostname}:5001/api`;

export const API_BASE_URL = (configuredBaseUrl || localBaseUrl).replace(/\/$/, "");

let csrfToken = null;
let csrfTokenPromise = null;

function emitUnauthorized() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("internassist:unauthorized"));
  }
}

function isCsrfFailure(response, payload) {
  return response.status === 403 && payload?.error === "Invalid or missing CSRF token.";
}

export async function ensureCsrfToken() {
  if (csrfToken) return csrfToken;
  if (!csrfTokenPromise) {
    csrfTokenPromise = (async () => {
      const response = await fetch(`${API_BASE_URL}/auth/csrf`, { credentials: "include" });
      if (!response.ok) throw new Error("Unable to initialize a secure session.");
      const payload = await response.json();
      if (!payload?.csrf_token) throw new Error("The server returned an invalid secure session.");
      csrfToken = payload.csrf_token;
      return csrfToken;
    })().finally(() => { csrfTokenPromise = null; });
  }
  return csrfTokenPromise;
}

export function setCsrfToken(value) {
  csrfToken = value || null;
  csrfTokenPromise = null;
}

function getErrorMessage(payload, fallback) {
  return payload?.error || payload?.message || fallback;
}

export async function apiRequest(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const mutating = ["POST", "PUT", "PATCH", "DELETE"].includes(method);

  async function send(attempt = 0) {
    const token = mutating ? await ensureCsrfToken() : null;
    const response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: "include",
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
        ...(token ? { "X-CSRF-Token": token } : {}),
      },
    });

    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : null;

    // A server restart, expired cookie, or inactive-session cleanup can rotate the
    // session while this module still holds its previous token. The rejected
    // request has not reached the route handler, so it is safe to bootstrap a new
    // token and retry it exactly once.
    if (mutating && attempt === 0 && isCsrfFailure(response, payload)) {
      setCsrfToken(null);
      return send(1);
    }

    if (!response.ok) {
      const error = new Error(getErrorMessage(payload, `Request failed (${response.status}).`));
      error.status = response.status;
      error.payload = payload;
      if (response.status === 401) emitUnauthorized();
      throw error;
    }

    return payload;
  }

  return send();
}

export function uploadDocument(formData, onProgress) {
  async function send(attempt = 0) {
    const token = await ensureCsrfToken();
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("POST", `${API_BASE_URL}/documents`);
      request.withCredentials = true;
      request.setRequestHeader("X-CSRF-Token", token);

      request.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
      });

      request.addEventListener("load", async () => {
        let payload = null;
        try { payload = request.responseText ? JSON.parse(request.responseText) : null; } catch { /* handled below */ }
        if (request.status >= 200 && request.status < 300) {
          onProgress?.(100);
          resolve(payload);
          return;
        }
        if (attempt === 0 && request.status === 403 && payload?.error === "Invalid or missing CSRF token.") {
          setCsrfToken(null);
          try { resolve(await send(1)); } catch (error) { reject(error); }
          return;
        }
        if (request.status === 401) emitUnauthorized();
        const error = new Error(getErrorMessage(payload, `Upload failed (${request.status || "network error"}).`));
        error.status = request.status;
        error.payload = payload;
        reject(error);
      });

      request.addEventListener("error", () => reject(new Error("Unable to connect to the server.")));
      request.addEventListener("abort", () => reject(new Error("Upload cancelled.")));
      request.send(formData);
    });
  }

  return send();
}

export async function downloadDocument(item) {
  const response = await fetch(`${API_BASE_URL}/documents/${item.id}/download`, { credentials: "include" });
  if (!response.ok) {
    let payload = null;
    try { payload = await response.json(); } catch { /* use fallback */ }
    if (response.status === 401) emitUnauthorized();
    const error = new Error(getErrorMessage(payload, "Unable to download this document."));
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = window.document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = item.filename || item.title || "document";
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}
