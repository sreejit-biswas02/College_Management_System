import { apiRequest } from "./client.js";

export function loginRequest(email, password) {
  return apiRequest("/auth/login", {
    method: "POST",
    body: { email, password },
    auth: false,
  });
}

export function fetchCurrentUser() {
  return apiRequest("/auth/me", {
    method: "GET",
    auth: true,
  });
}
