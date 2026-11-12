import { t, locale, controlled } from "./i18n.mjs";
import { scopeParams } from "./model.mjs";
export class PageError extends Error {
  constructor(code, message) { super(message); this.code = String(code || "unavailable"); }
}
export function pageError(error) {
  if (error instanceof PageError) return error;
  const status = error?.status ?? error?.statusCode ?? error?.response?.status;
  const message = typeof error?.message === "string" ? error.message : t("宿主请求失败，请检查插件连接。");
  // AstrBot's parent bridge serializes HTTP failures as message-only Errors.
  const marker = message.match(/^\[livingemotion:(unauthorized|forbidden|edit_disabled|version_conflict|generation_in_progress|validation_error|unavailable)\]\s*/);
  const httpStatus = status ?? Number(message.match(/^Request failed with status code (401|403|404|405|409)$/)?.[1]);
  const code = marker?.[1] || (httpStatus === 401 ? "unauthorized" : httpStatus === 403 ? "forbidden" :
    httpStatus === 409 ? "version_conflict" : httpStatus === 404 ? "not_found" : httpStatus === 405 ? "method_not_allowed" : error?.code || "bridge_error");
  return new PageError(code, marker ? message.slice(marker[0].length) : message);
}
export function unwrap(response) {
  if (!response || typeof response !== "object") throw new PageError("invalid_response", t("宿主返回了无效响应。"));
  if (response.ok === false || response.status === "error" || response.status === 401 ||
      response.status === 403 || response.status === 409) throw pageError(response);
  if (response.status === "ok" || response.ok === true) {
    if (!response.data || typeof response.data !== "object") throw new PageError("invalid_response", t("宿主响应缺少数据。"));
    return response.data;
  }
  return response;
}
export function createApi(resolveBridge, timeout = 15000) {
  async function call(method, path, payload, wait = timeout) {
    const bridge = resolveBridge();
    if (!bridge || typeof bridge[method] !== "function") {
      throw new PageError("missing_bridge", t("未检测到 AstrBot 页面连接。请从已登录的宿主插件详情页打开。"));
    }
    let timer;
    try {
      const response = await Promise.race([
        Promise.resolve().then(() => bridge[method](path, payload)),
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new PageError("timeout",
            method === "apiPost" ? t("请求超时，执行结果不明。请核对记录，不要重复提交。") : t("读取超时，请手动刷新。"))), wait);
        }),
      ]);
      return unwrap(response);
    } catch (error) { throw pageError(error); }
    finally { clearTimeout(timer); }
  }
  return {
    state: selection => call("apiGet", "console/state", scopeParams(selection)),
    scopes: () => call("apiGet", "console/scopes", {}),
    config: selection => call("apiGet", "console/config", scopeParams(selection)),
    configuration: selection => call("apiGet", "console/configuration", scopeParams(selection)),
    settingsOptions: () => call("apiGet", "console/settings-options", {}),
    personaDescription: personaId => call("apiGet", "console/persona-description",
      { persona_id: String(personaId) }),
    styleSummary: personaId => call("apiGet", "console/style-summary",
      { persona_id: String(personaId) }),
    saveStyleSummary: body => call("apiPost", "console/style-summary-save", body),
    relationships: params => call("apiGet", "console/relationships", params),
    relationship: body => call("apiPost", "console/relationship", body),
    energy: params => call("apiGet", "console/energy", params),
    records: params => call("apiGet", "console/records", params),
    save: body => call("apiPost", "console/config", body),
    preview: contextId => call("apiPost", "console/preview", { context_id: contextId }),
    simulate: body => call("apiPost", "console/behavior-simulate", body, 100000),
    action: body => call("apiPost", "console/action", body),
    experienceGenerate: body => call("apiPost", "console/experience-generate", body),
    experienceTask: requestId => call("apiGet", "console/experience-task", { request_id: requestId }),
    memorySync: body => call("apiPost", "console/memory-sync", body),
    emotionImages: () => call("apiGet", "console/emotion-images", {}),
    emotionImage: (mood, index) => call("apiGet", "console/emotion-image",
      index ? { mood, index: String(index) } : { mood }),
    saveEmotionImage: body => call("apiPost", "console/emotion-image-save", body),
  };
}
