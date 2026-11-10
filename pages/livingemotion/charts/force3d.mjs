// 无额外依赖的三轴布局。初始位置由账号决定，翻页不会重新随机排布。
export const MAX_RADIUS = 230;
export const MIN_RADIUS = 68;
export const MIN_SPACING = 20;
function randomFor(id) {
  let seed = 2166136261;
  for (const ch of String(id)) seed = Math.imul(seed ^ ch.charCodeAt(0), 16777619) >>> 0;
  return () => ((seed = Math.imul(seed, 1664525) + 1013904223 >>> 0) / 4294967296);
}
export function seedPeople(items) {
  return items.map(item => {
    const random = randomFor(item.id), azimuth = random() * Math.PI * 2;
    const height = random() * 1.8 - .9, lateral = Math.sqrt(1 - height * height);
    const affinity = Number.isFinite(item.score) ? Math.max(0, Math.min(100, item.score)) / 100 : .5;
    const radius = 95 + (1 - affinity) * 70 + random() * 55;
    return { ...item, x: 360 + Math.cos(azimuth) * radius * lateral,
      y: 210 + height * radius, depth: Math.sin(azimuth) * radius * lateral,
      radius, vx: 0, vy: 0, vz: 0, anchorAngle: azimuth };
  });
}
export function constrain3D(item) {
  let dx = item.x - 360, dy = item.y - 210, dz = item.depth;
  const length = Math.hypot(dx, dy, dz);
  if (!length) { dx = Math.cos(item.anchorAngle || 0); dy = 0; dz = Math.sin(item.anchorAngle || 0); }
  const radius = Math.max(MIN_RADIUS, Math.min(MAX_RADIUS, length));
  const factor = radius / (length || 1);
  item.x = 360 + dx * factor; item.y = 210 + dy * factor; item.depth = dz * factor;
}
export function separate3D(items, passes = 3) {
  for (let pass = 0; pass < passes; pass++) {
    for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
      const a = items[i], b = items[j];
      let dx = b.x - a.x, dy = b.y - a.y, dz = b.depth - a.depth;
      const length = Math.hypot(dx, dy, dz);
      if (length >= MIN_SPACING) continue;
      if (!length) { dx = Math.cos(i + j); dy = .5; dz = Math.sin(i + j); }
      const shift = (MIN_SPACING - length + .01) / (length || Math.hypot(dx, dy, dz)) / 2;
      if (a.fx == null) { a.x -= dx * shift; a.y -= dy * shift; a.depth -= dz * shift; }
      if (b.fx == null) { b.x += dx * shift; b.y += dy * shift; b.depth += dz * shift; }
    }
    items.forEach(constrain3D);
  }
}
export function createForce3D(items, edges) {
  const byId = new Map(items.map(item => [item.id, item]));
  const links = edges.map(edge => [byId.get(edge.source), byId.get(edge.target)])
    .filter(([a, b]) => a && b);
  let steps = 0;
  return {
    tick(count = 1) {
      for (let tick = 0; tick < count; tick++) {
        const heat = Math.max(.12, Math.exp(-steps++ / 65));
        for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
          const a = items[i], b = items[j], dx = b.x - a.x, dy = b.y - a.y, dz = b.depth - a.depth;
          const d2 = Math.max(16, dx * dx + dy * dy + dz * dz);
          const force = Math.min(.025, 220 / (d2 * Math.sqrt(d2))) * heat;
          a.vx -= dx * force; a.vy -= dy * force; a.vz -= dz * force;
          b.vx += dx * force; b.vy += dy * force; b.vz += dz * force;
        }
        for (const [a, b] of links) {
          const dx = b.x - a.x, dy = b.y - a.y, dz = b.depth - a.depth;
          const d = Math.hypot(dx, dy, dz) || 1, pull = (d - 55) / d * .009 * heat;
          a.vx += dx * pull; a.vy += dy * pull; a.vz += dz * pull;
          b.vx -= dx * pull; b.vy -= dy * pull; b.vz -= dz * pull;
        }
        for (const item of items) {
          if (item.fx != null) { item.vx = item.vy = item.vz = 0; continue; }
          const dx = item.x - 360, dy = item.y - 210, dz = item.depth;
          const d = Math.hypot(dx, dy, dz) || 1, spring = (d - item.radius) / d * .006 * heat;
          item.vx = (item.vx - dx * spring) * .78;
          item.vy = (item.vy - dy * spring) * .78;
          item.vz = (item.vz - dz * spring) * .78;
          item.x += item.vx; item.y += item.vy; item.depth += item.vz;
        }
        separate3D(items, 1);
      }
    },
  };
}
