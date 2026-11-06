import { text } from "./model.mjs";
export function node(tag, content, className) {
  const element = document.createElement(tag);
  if (content !== undefined) element.textContent = text(content, "");
  if (className) element.className = className;
  return element;
}
export function button(label, handler, className) {
  const element = node("button", label, className);
  element.type = "button";
  element.addEventListener("click", handler);
  return element;
}
export function svgNode(tag, attrs = {}, content) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
  if (content !== undefined) element.textContent = String(content);
  return element;
}
export function labelled(labelText, input) {
  const wrapper = node("div", undefined, "scope-field");
  const label = node("label", labelText); label.htmlFor = input.id;
  wrapper.append(label, input);
  return wrapper;
}
