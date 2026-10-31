const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

export const API_BASE_URL = (configuredBaseUrl || "http://localhost:5001/api").replace(/\/$/, "");

function getErrorMessage(payload, fallback) {
  return payload?.error || payload?.message || fallback;
}

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const error = new Error(getErrorMessage(payload, `Request failed (${response.status}).`));
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export function uploadDocument(formData, onProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/documents`);
    request.withCredentials = true;

    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    });

    request.addEventListener("load", () => {
      let payload = null;
      try { payload = request.responseText ? JSON.parse(request.responseText) : null; } catch { /* handled below */ }
      if (request.status >= 200 && request.status < 300) {
        onProgress?.(100);
        resolve(payload);
      } else {
        const error = new Error(getErrorMessage(payload, `Upload failed (${request.status || "network error"}).`));
        error.status = request.status;
        reject(error);
      }
    });

    request.addEventListener("error", () => reject(new Error("Unable to connect to the server.")));
    request.addEventListener("abort", () => reject(new Error("Upload cancelled.")));
    request.send(formData);
  });
}

export async function downloadDocument(item) {
  const response = await fetch(`${API_BASE_URL}/documents/${item.id}/download`, { credentials: "include" });
  if (!response.ok) {
    let payload = null;
    try { payload = await response.json(); } catch { /* use fallback */ }
    throw new Error(getErrorMessage(payload, "Unable to download this document."));
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = window.document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = item.filename || item.title || "document";
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
