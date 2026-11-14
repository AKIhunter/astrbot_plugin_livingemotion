import { t } from "./i18n.mjs?v=eff0d6f932b0";
import { node, button } from "./dom.mjs?v=eff0d6f932b0";
import { PageError, pageError } from "./api.mjs?v=eff0d6f932b0";

// 图片由管理员自己维护：文件名与情绪名一致（开心.png / 开心-2.webp …）。
// 上限与后端 storage/emotion_images.py 保持一致，前端先拦一次，避免白跑一趟。
export const MAX_BYTES = 512 * 1024;
export const ACCEPT = "image/png,image/jpeg,image/webp";
const ROTATE_MS = 6000;

const cache = new Map();
let catalogue = null;

export function resetEmotionImages() {
  cache.clear();
  catalogue = null;
}

export async function loadCatalogue(api, force = false) {
  if (catalogue && !force) return catalogue;
  catalogue = await api.emotionImages();
  return catalogue;
}

function moodEntry(key) {
  return (catalogue?.moods ?? []).find(item => item.key === key) ?? null;
}

/** 取某个情绪的全部图片（data URL 按需取，不塞进 state 主载荷）。 */
export async function loadMoodImages(api, key, force = false) {
  if (cache.has(key) && !force) return cache.get(key);
  const entry = moodEntry(key);
  const images = [];
  for (const file of entry?.files ?? []) {
    try {
      const data = await api.emotionImage(key, file.index);
      if (data?.data_url) images.push({ index: file.index, name: file.name, url: data.data_url });
    } catch (error) {
      if (error.code === "unauthorized" || error.code === "forbidden") throw error;
      // 单张读失败不拖垮整张卡片：其余图片继续轮播。
    }
  }
  cache.set(key, images);
  return images;
}

function fileToDataUrl(file, isCurrent) {
  return new Promise((resolve, reject) => {
    if (!ACCEPT.split(",").includes(file.type)) {
      reject(new PageError("validation_error", t("只支持 PNG、JPEG 与 WebP 图片。"))); return;
    }
    if (file.size > MAX_BYTES) {
      reject(new PageError("validation_error", t("图片超过 512 KB，请先压缩后再上传。"))); return;
    }
    if (!isCurrent()) { resolve(null); return; }
    const reader = new FileReader();
    reader.onerror = () => reject(new PageError("validation_error", t("读取图片失败，请重试。")));
    reader.onload = () => resolve(String(reader.result || ""));
    reader.readAsDataURL(file);
  });
}

/**
 * 情绪卡片：固定 16:9 容器 + object-fit: cover 的图片 / 渐变占位。
 * 单层结构（不套卡片），TA 首屏与情绪页共用同一套图片与轮播逻辑。
 */
export function moodCard({ api, moodKey, moodName, canWrite, onError }) {
  const root = node("figure", undefined, "mood-card");
  root.dataset.mood = moodKey;
  const frame = node("div", undefined, "mood-frame");
  const placeholder = node("div", undefined, "mood-placeholder");
  placeholder.append(node("span", moodName, "mood-placeholder-name"),
    node("span", t("还没有上传图片"), "micro"));
  const image = node("img", undefined, "mood-image");
  image.alt = t("{0} 的情绪配图", [moodName]);
  image.decoding = "async";
  image.hidden = true;
  // 加载失败退回占位块，而不是留一个破图标。
  image.addEventListener("error", () => { image.hidden = true; placeholder.hidden = false; });
  const dots = node("div", undefined, "mood-dots");
  const status = node("p", "", "mood-status micro");
  status.setAttribute("role", "status");
  const tools = node("div", undefined, "mood-tools");
  frame.append(placeholder, image, dots);
  const caption = node("figcaption", undefined, "mood-caption");
  caption.append(node("span", moodName, "mood-caption-name"),
    node("span", t("按情绪名匹配 · 建议 320×180"), "micro"));
  // 右侧文字段：情绪名 + 用法提示 + 状态 + 操作，和图片并排但不套第二层卡片。
  const side = node("div", undefined, "mood-side");
  side.append(caption, status);
  if (canWrite()) side.append(tools);
  root.append(frame, side);

  let images = [], current = 0, timer = null, disposed = false, hovering = false, busy = false;
  let syncTools = () => {};
  root.addEventListener("pointerenter", () => { hovering = true; });
  root.addEventListener("pointerleave", () => { hovering = false; });
  root.addEventListener("focusin", () => { hovering = true; });
  root.addEventListener("focusout", () => { hovering = false; });

  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const paint = () => {
    const active = images[current];
    dots.replaceChildren();
    syncTools();
    if (!active) { image.hidden = true; placeholder.hidden = false; return; }
    image.src = active.url;
    image.hidden = false; placeholder.hidden = true;
    if (images.length > 1) {
      images.forEach((item, index) => {
        const dot = button("", () => { current = index; paint(); restart(); }, "mood-dot");
        dot.setAttribute("aria-label", t("第 {0} 张", [index + 1]));
        dot.setAttribute("aria-pressed", String(index === current));
        if (index === current) dot.classList.add("active");
        dots.append(dot);
      });
    }
    status.textContent = images.length > 1 ? t("{0} / {1}", [current + 1, images.length]) : status.textContent;
  };
  const stop = () => { clearInterval(timer); timer = null; };
  const restart = () => {
    stop();
    if (images.length < 2 || reduced() || disposed) return;
    timer = setInterval(() => {
      if (hovering || document.hidden || busy) return;
      current = (current + 1) % images.length; paint();
    }, ROTATE_MS);
  };
  const refresh = async (force = false) => {
    if (disposed) return;
    status.textContent = t("图片读取中…");
    try {
      await loadCatalogue(api, force);
      images = await loadMoodImages(api, moodKey, force);
      if (disposed) return;
      if (current >= images.length) current = 0;
      paint(); restart();
      status.textContent = images.length ? "" : t("可以上传一张图片作为这个情绪的配图。");
    } catch (error) {
      if (disposed) return;
      status.textContent = t("图片读取失败");
      status.append(" ", button(t("重试"), () => refresh(true), "mood-retry"));
      onError?.(error);
    }
  };

  if (canWrite()) {
    const input = node("input");
    input.type = "file"; input.accept = ACCEPT; input.hidden = true;
    input.setAttribute("aria-label", t("上传 {0} 的配图", [moodName]));
    const upload = button(t("上传图片"), () => input.click(), "mood-upload");
    const remove = button(t("删除"), async () => {
      if (busy || !images.length) return;
      busy = true; syncTools();
      status.textContent = t("正在删除…");
      try {
        await api.saveEmotionImage({ mood: moodKey, index: images[current]?.index, remove: true });
        current = 0; await refresh(true);
      } catch (error) {
        status.textContent = pageError(error).message;
        onError?.(error);
      } finally { busy = false; if (!disposed) { syncTools(); status.textContent = t("已删除。"); } }
    }, "mood-remove");
    const preview = button(t("预览"), () => openPreview(images[current]?.url, moodName), "mood-preview");
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      input.value = "";
      if (!file || busy) return;
      busy = true; syncTools();
      root.classList.add("uploading"); status.textContent = t("正在上传…");
      try {
        const dataUrl = await fileToDataUrl(file, () => !disposed);
        if (!dataUrl) return;
        const result = await api.saveEmotionImage({ mood: moodKey, data_url: dataUrl });
        if (disposed) return;
        current = Math.max(0, (result?.index ?? 1) - 1);
        await refresh(true);
        status.textContent = t("已保存。");
      } catch (error) {
        status.textContent = pageError(error).message;
        onError?.(error);
      } finally {
        busy = false; root.classList.remove("uploading");
        if (!disposed) syncTools();
      }
    });
    syncTools = () => {
      const has = images.length > 0;
      upload.disabled = busy; remove.disabled = busy || !has; preview.disabled = !has;
      upload.textContent = has ? t("替换图片") : t("上传图片");
    };
    tools.append(upload, preview, remove, input);
    syncTools();
  }

  refresh();
  root.dispose = () => { disposed = true; stop(); };
  return root;
}

function openPreview(url, name) {
  if (!url) return;
  const dialog = node("dialog", undefined, "mood-preview-dialog");
  const body = node("div", undefined, "mood-preview-body");
  const image = node("img");
  image.src = url; image.alt = t("{0} 的配图预览", [name]);
  const close = button(t("关闭"), () => { dialog.close(); dialog.remove(); });
  body.append(image, close); dialog.append(body);
  document.body.append(dialog);
  dialog.showModal();
  dialog.addEventListener("cancel", () => dialog.remove());
}
