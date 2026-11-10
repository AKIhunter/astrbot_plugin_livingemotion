// 三方核对：只合并未编辑字段；同字段的其他修改必须由管理员复核。
export function reconcileDraft(draft, baseline, current, allowed) {
  const patch = Object.create(null), conflicts = [];
  for (const [key, value] of Object.entries(draft)) {
    if (!allowed.has(key) || value === current[key]) continue;
    patch[key] = value;
    if (!Object.hasOwn(baseline, key) || baseline[key] !== current[key]) {
      conflicts.push({ key, current: current[key], draft: value });
    }
  }
  return { patch, conflicts };
}
