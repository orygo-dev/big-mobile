import axios from "axios";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").trim().replace(/\/+$/, "");
export const API = `${BACKEND_URL}/api`;

export const TOKEN_KEY = "fc_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

const api = axios.create({ baseURL: API, withCredentials: true, timeout: 30000 });

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Array endpoints are bounded on the server. Existing list/dropdown screens fetch
// subsequent pages so records beyond the first 500 are still reachable.
api.interceptors.response.use(async (response) => {
  if (!Array.isArray(response.data) || response.config.params?.page != null || !response.headers['x-next-page']) return response;
  const result = [...response.data];
  let next = response.headers['x-next-page'];
  let previous = 1;
  while (next) {
    const page = Number(next);
    if (!Number.isInteger(page) || page <= previous) throw new Error('Urutan halaman data tidak valid. Coba muat ulang.');
    const following = await api.get(response.config.url, {...response.config, params: {...response.config.params, page}});
    result.push(...following.data);
    previous = page; next = following.headers['x-next-page'];
  }
  response.data = result;
  return response;
}, (error) => {
  if (error.response?.status === 401 && !error.config?.url?.endsWith('/auth/login')) {
    clearToken();
    window.dispatchEvent(new Event('big-mobile-session-expired'));
  }
  return Promise.reject(error);
});

export function formatApiError(detail) {
  if (detail == null) return "Terjadi kesalahan. Silakan coba lagi.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export const errMsg = (e) => {
  if (e?.response?.data?.detail != null) return formatApiError(e.response.data.detail);
  if (!e?.response && (e?.code === "ERR_NETWORK" || e?.message === "Network Error"))
    return "Layanan aplikasi belum dapat dihubungi. Silakan coba lagi dalam beberapa saat.";
  if (e?.code === "ECONNABORTED" || e?.code === "ETIMEDOUT")
    return "Layanan membutuhkan waktu terlalu lama untuk merespons. Silakan coba lagi.";
  return e?.message || "Terjadi kesalahan. Silakan coba lagi.";
};

// HttpOnly session cookie authenticates images/iframes without tokens in URLs.
export const fileUrl = (url) => {
  if (!url) return "";
  if (!url.startsWith("/api/files/")) return url;
  return `${BACKEND_URL}${url}`;
};

export default api;
