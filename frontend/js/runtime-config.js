// Runtime API configuration.
// Uses localhost for local development and same-origin /api/v1 on deployed hosts
// unless explicitly overridden by frontend/build.sh.
(function configureRuntimeApi() {
  if (window.CMS_CONFIG && window.CMS_CONFIG.API_BASE_URL) {
    return;
  }
  const host = typeof window !== "undefined" ? window.location.hostname : "";
  const isLocal = host === "127.0.0.1" || host === "localhost" || host === "";
  window.CMS_CONFIG = {
    API_BASE_URL: isLocal ? "http://127.0.0.1:8000/api/v1" : "/api/v1",
  };
})();
