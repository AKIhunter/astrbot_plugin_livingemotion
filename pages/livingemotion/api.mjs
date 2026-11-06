export class PageError extends Error {
  constructor(code, message) { super(message); this.code = String(code || "unavailable"); }
}
export function pageError(error) {
  if (error instanceof PageError) return error;
  const status = error?.status ?? error?.statusCode ?? error?.response?.status;
  const message = typeof error?.message === "string" ? error.message : "宿主请求失败，请检查插件连接。";
  // AstrBot's parent bridge serializes HTTP failures as message-only Errors.
  const marker = message.match(/^\[livingemotion:(unauthorized|forbidden|version_conflict|validation_error|unavailable)\]\s*/);
  const httpStatus = status ?? Number(message.match(/^Request failed with status code (401|403|409)$/)?.[1]);
  const code = marker?.[1] || (httpStatus === 401 ? "unauthorized" : httpStatus === 403 ? "forbidden" :
    httpStatus === 409 ? "version_conflict" : error?.code || "bridge_error");
  return new PageError(code, marker ? message.slice(marker[0].length) : message);
}
export function unwrap(response) {
  if (!response || typeof response !== "object") throw new PageError("invalid_response", "宿主返回了无效响应。");
  if (response.ok === false || response.status === "error" || response.status === 401 ||
      response.status === 403 || response.status === 409) throw pageError(response);
  if (response.status === "ok" || response.ok === true) {
    if (!response.data || typeof response.data !== "object") throw new PageError("invalid_response", "宿主响应缺少数据。");
    return response.data;
  }
  return response;
}
export function createApi(resolveBridge, timeout = 15000) {
  async function call(method, path, payload) {
    const bridge = resolveBridge();
    if (!bridge || typeof bridge[method] !== "function") {
      throw new PageError("missing_bridge", "未检测到 AstrBot 页面连接。请从已登录的宿主插件详情页打开。");
    }
    let timer;
    try {
      const response = await Promise.race([
        Promise.resolve().then(() => bridge[method](path, payload)),
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new PageError("timeout",
            method === "apiPost" ? "请求超时，执行结果不明。请核对记录，不要重复提交。" : "读取超时，请手动刷新。")), timeout);
        }),
      ]);
      return unwrap(response);
    } catch (error) { throw pageError(error); }
    finally { clearTimeout(timer); }
  }
  return {
    state: contextId => call("apiGet", "console/state", contextId ? { context_id: contextId } : {}),
    records: params => call("apiGet", "console/records", params),
    save: body => call("apiPost", "console/config", body),
    preview: contextId => call("apiPost", "console/preview", { context_id: contextId }),
    action: body => call("apiPost", "console/action", body),
  };
}
