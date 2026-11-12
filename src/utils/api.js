export function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_URL;
  if (configured) {
    return configured.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined" && window.location?.hostname === "127.0.0.1") {
    return "http://127.0.0.1:5001";
  }
  return "http://localhost:5001";
}

export async function parseJsonResponse(response, fallbackError = "Request failed.") {
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message = data?.error || data?.message || fallbackError;
    throw new Error(message);
  }

  if (!data || typeof data !== "object") {
    throw new Error("The server returned an invalid response. Please try again.");
  }

  return data;
}

