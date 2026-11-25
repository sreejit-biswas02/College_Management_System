import { fetchCurrentUser, loginRequest } from "../api/authApi.js";
import { CONFIG } from "../config.js";

let currentUser = null;

export function getToken() {
  return sessionStorage.getItem(CONFIG.TOKEN_STORAGE_KEY);
}

export function getCurrentUser() {
  if (currentUser) {
    return currentUser;
  }
  const raw = sessionStorage.getItem(CONFIG.USER_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    currentUser = JSON.parse(raw);
    return currentUser;
  } catch {
    return null;
  }
}

export function isAuthenticated() {
  return Boolean(getToken() && getCurrentUser());
}

export function clearSession() {
  currentUser = null;
  sessionStorage.removeItem(CONFIG.TOKEN_STORAGE_KEY);
  sessionStorage.removeItem(CONFIG.USER_STORAGE_KEY);
}

export async function login(email, password) {
  const data = await loginRequest(email, password);
  sessionStorage.setItem(CONFIG.TOKEN_STORAGE_KEY, data.access_token);
  const user = data.user || (await fetchCurrentUser());
  currentUser = user;
  sessionStorage.setItem(CONFIG.USER_STORAGE_KEY, JSON.stringify(user));
  return user;
}

export async function restoreSession() {
  const token = getToken();
  if (!token) {
    clearSession();
    return null;
  }
  try {
    const user = await fetchCurrentUser();
    currentUser = user;
    sessionStorage.setItem(CONFIG.USER_STORAGE_KEY, JSON.stringify(user));
    return user;
  } catch {
    clearSession();
    return null;
  }
}

export function logout() {
  clearSession();
}
