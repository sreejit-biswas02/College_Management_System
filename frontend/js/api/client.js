import { CONFIG } from "../config.js";

export class ApiError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

export function getStoredToken() {
  return sessionStorage.getItem(CONFIG.TOKEN_STORAGE_KEY);
}

export async function apiRequest(path, options = {}) {
  const {
    method = "GET",
    body = null,
    headers = {},
    auth = true,
    timeoutMs = CONFIG.REQUEST_TIMEOUT_MS,
  } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const requestHeaders = {
    Accept: "application/json",
    ...headers,
  };

  if (body !== null && !(body instanceof FormData)) {
    requestHeaders["Content-Type"] = "application/json";
  }

  if (auth) {
    const token = getStoredToken();
    if (token) {
      requestHeaders.Authorization = `Bearer ${token}`;
    }
  }

  try {
    const response = await fetch(`${CONFIG.API_BASE_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: body !== null && !(body instanceof FormData) ? JSON.stringify(body) : body,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.status === 204) {
      return null;
    }

    let data = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    }

    if (!response.ok) {
      const detail =
        (data && (data.detail || data.message)) ||
        `Request failed with status ${response.status}.`;

      if (response.status === 401 && auth && unauthorizedHandler) {
        unauthorizedHandler("Your session has expired. Please sign in again.");
      }

      throw new ApiError(
        typeof detail === "string" ? detail : JSON.stringify(detail),
        response.status,
        data
      );
    }

    return data;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof ApiError) {
      throw err;
    }
    if (err.name === "AbortError") {
      throw new ApiError("Request timed out. Please try again.", 0);
    }
    throw new ApiError(
      "Unable to reach the server. Please check your connection.",
      0
    );
  }
}
