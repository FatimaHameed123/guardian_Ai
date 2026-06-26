const FLASK_BASE = import.meta.env.VITE_API_URL || "http://localhost:5000";

let jwtToken = null;
let csrfToken = null;

export function setAuth(jwt, csrf) {
  jwtToken = jwt;
  if (csrf) csrfToken = csrf;
}

export function applyCsrf(data) {
  if (data?.csrf_token) csrfToken = data.csrf_token;
}

export function clearAuth() {
  jwtToken = null;
  csrfToken = null;
}

function headers() {
  const h = { "Content-Type": "application/json" };
  if (jwtToken) h.Authorization = `Bearer ${jwtToken}`;
  return h;
}

export async function apiLogin(username, password) {
  const res = await fetch(`${FLASK_BASE}/login`, {
    method: "POST",
    credentials: "include",
    headers: headers(),
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (data.status === "success") setAuth(data.token, data.csrf_token);
  return data;
}

export async function apiChat(message) {
  const res = await fetch(`${FLASK_BASE}/chat_predict`, {
    method: "POST",
    credentials: "include",
    headers: headers(),
    body: JSON.stringify({ message }),
  });
  return res.json();
}

export async function apiHeatmap(params = {}) {
  const q = new URLSearchParams(params).toString();
  const res = await fetch(`${FLASK_BASE}/api/heatmap?${q}`, { headers: headers() });
  return res.json();
}

export async function apiDashboard() {
  const res = await fetch(`${FLASK_BASE}/api/analytics/dashboard`, { headers: headers() });
  return res.json();
}

export async function apiHealth() {
  const res = await fetch(`${FLASK_BASE}/health`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${FLASK_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: headers(),
    body: JSON.stringify({ ...body, csrf_token: csrfToken }),
  });
  const data = await res.json();
  applyCsrf(data);
  return data;
}

export async function apiGetCases() {
  const res = await fetch(`${FLASK_BASE}/cases`, { headers: headers() });
  return res.json();
}

export async function apiAddCase(payload) {
  return apiPost("/cases/add", payload);
}

export async function apiUpdateCase(caseId, payload) {
  return apiPost(`/cases/update/${caseId}`, payload);
}

export async function apiDeleteCase(caseId) {
  return apiPost(`/cases/delete/${caseId}`, {});
}

export async function apiGetCaseDetails(caseId) {
  const res = await fetch(`${FLASK_BASE}/cases/${caseId}/details`, { headers: headers() });
  return res.json();
}

export async function apiSaveCaseDetails(caseId, payload) {
  return apiPost(`/cases/${caseId}/details`, payload);
}

export async function apiDbInfo() {
  const res = await fetch(`${FLASK_BASE}/api/db/info`, { headers: headers() });
  return res.json();
}

export { FLASK_BASE };
