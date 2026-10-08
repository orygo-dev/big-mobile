// These cases exercise the same-origin default regardless of the local .env.
import api, { API, fileUrl, errMsg, formatApiError, setToken, clearToken } from "./api";

afterEach(() => clearToken());

test("API defaults to the same origin", () => {
  expect(API).toBe("/api");
});

test("file URLs preserve data URLs and external images", () => {
  expect(fileUrl("data:image/png;base64,abc")).toBe("data:image/png;base64,abc");
  expect(fileUrl("https://example.com/logo.png")).toBe("https://example.com/logo.png");
});

test("protected file URLs preserve queries without exposing access tokens", () => {
  setToken("a+b&c");
  expect(fileUrl("/api/files/photo.jpg?download=1")).toBe("/api/files/photo.jpg?download=1");
});

test("missing tokens are not appended as null", () => {
  expect(fileUrl("/api/files/photo.jpg")).toBe("/api/files/photo.jpg");
});

test("unreachable services have a readable Indonesian message", () => {
  expect(errMsg(new Error("Network Error"))).toContain("Layanan aplikasi belum dapat dihubungi");
  expect(errMsg({ code: "ERR_NETWORK" })).toContain("Layanan aplikasi belum dapat dihubungi");
});

test("server errors retain their specific details", () => {
  expect(errMsg({ code: "ERR_NETWORK", response: { data: { detail: "Akun nonaktif" } } })).toBe("Akun nonaktif");
});

test("timeouts are distinct from invalid login credentials", () => {
  expect(errMsg({ code: "ECONNABORTED" })).toContain("terlalu lama");
});

test("validation errors become readable text", () => {
  expect(formatApiError([{ msg: "Required" }, { msg: "Invalid" }])).toBe("Required Invalid");
});

test("list screens include records beyond the first server page", async () => {
  const pages=[];
  const adapter=async (config) => {const page=config.params?.page || 1;pages.push(page);return {data:[{id:page}],status:200,statusText:'OK',config,headers:{'x-next-page':page===1?'2':''}};};
  const response=await api.get('/clients',{adapter});
  expect(response.data).toEqual([{id:1},{id:2}]);expect(pages).toEqual([1,2]);
});

test("explicit pagination fetches only the requested page", async () => {
  const adapter=async config=>({data:[{id:1}],status:200,statusText:'OK',config,headers:{'x-next-page':'2'}});
  expect((await api.get('/clients',{adapter,params:{page:1}})).data).toEqual([{id:1}]);
});

test("expired authentication clears the stored token and notifies the auth provider", async () => {
  setToken('old-session');const listener=vi.fn();window.addEventListener('big-mobile-session-expired',listener);
  try {
    const adapter=async config=>Promise.reject({config,response:{status:401}});
    await expect(api.get('/my/profile',{adapter})).rejects.toMatchObject({response:{status:401}});
    expect(localStorage.getItem('fc_token')).toBeNull();expect(listener).toHaveBeenCalledOnce();
  } finally {window.removeEventListener('big-mobile-session-expired',listener);}
});
