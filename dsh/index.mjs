import path from 'node:path';
import { createHash } from 'node:crypto';
import z from '@deepseek-ai/schemastery';
import { WorkerClient } from './worker-client.mjs';

export const name = 'dsh-livingemotion';
export const inject = ['agents', 'systemPrompt'];
export const Config = z.object({
  enabled: z.boolean().default(true).description('开启会话情绪；配置在本插件。关闭后不更新、不注入。'),
  python: z.string().default('python3').description('本机 Python 3.11+ 可执行文件。'),
  dataDir: z.string().default('.dsh/livingemotion').description('DSH 独立状态目录，不填 AstrBot 数据目录。'),
  proactiveEnabled: z.boolean().default(false).description('开启后可信 Host 插件通过 livingEmotion.sendText 主动发送；本版不自动调度。'),
});

const requiredText = (value, name) => {
  if (typeof value !== 'string' || !value.trim() || value.length > 512) throw Error(`invalid_${name}`);
  return value;
};
export function normalizeConfig(config = {}) {
  for (const key of ['enabled', 'proactiveEnabled'])
    if (config[key] !== undefined && typeof config[key] !== 'boolean') throw Error(`invalid_${key}`);
  return { enabled: config.enabled ?? true, proactiveEnabled: config.proactiveEnabled ?? false,
    python: requiredText(config.python ?? 'python3', 'python'),
    dataDir: path.resolve(requiredText(config.dataDir ?? '.dsh/livingemotion', 'dataDir')) };
}
export const userMessages = messages => (messages ?? []).filter(message =>
  message?.role === 'user' && message.source?.kind === 'user' && typeof message.id === 'string');
export const messageText = message => (message.content ?? [])
  .filter(block => block.type === 'text').map(block => block.text).join('\n');

export async function apply(ctx, input = {}) {
  const config = normalizeConfig(input);
  if (!config.enabled) return;
  const logger = ctx.logger(name);
  const worker = new WorkerClient(config.python, config.dataDir);
  ctx.effect(() => () => worker.stop());
  await worker.call('ping');
  const prompts = new Map();
  const agents = new Map();
  const sends = new Map();
  const sendControllers = new Set();
  let disposed = false;
  let bridge;
  const bridgeScope = ctx.inject(['dshIm'], bridgeCtx => {
    bridge = bridgeCtx.dshIm;
    bridgeCtx.effect(() => () => { bridge = undefined; });
  });
  await bridgeScope.await();
  function attach(agent) {
    if (agents.get(agent.id)?.agent === agent) return;
    agents.get(agent.id)?.dispose();
    const dispose = agent.ctx.systemPrompt.context({
      name: 'livingEmotion', order: 80, interpolate: false,
      text: () => prompts.get(agent.id) ?? '',
    });
    agents.set(agent.id, { agent, dispose });
  }
  const logicalContext = agentId => ({
    bot_id: 'dsh', persona_id: agentId, adapter_id: 'dsh-agent',
    platform: 'dsh', scene_kind: 'private', scene_id: agentId,
    // This is a logical session participant, never a guessed QQ sender.
    account_id: 'session-user', instance_id: config.dataDir,
  });
  async function state(agent, event, native = false, context = logicalContext(agent.id), signal) {
    const result = await worker.call('state', { context, event, native, now: Date.now() / 1000 }, signal);
    if (!disposed && agents.get(agent.id)?.agent === agent && !signal?.aborted)
      prompts.set(agent.id, result.prompt);
    return result;
  }
  ctx.on('agent/created', async ({ agent }) => {
    attach(agent);
    await state(agent);
  });
  ctx.on('agent/disposed', ({ agent }) => {
    if (agents.get(agent.id)?.agent !== agent) return;
    agents.get(agent.id).dispose();
    agents.delete(agent.id);
    prompts.delete(agent.id);
  });
  for (const agent of ctx.agents.list()) {
    attach(agent);
    await state(agent);
  }
  ctx.on('agent/pre-step', async (payload, next) => {
    const decision = await next();
    if (decision.kind !== 'enter' || payload.signal?.aborted) return decision;
    attach(payload.agent);
    try {
      const messages = userMessages(decision.messages);
      if (!messages.length) await state(payload.agent, undefined, false, undefined, payload.signal);
      for (const message of messages) await state(payload.agent, {
        event_id: message.id, source_id: message.id, producer: name,
        event_type: 'human_message', actor_role: 'human', actor_id: 'session-user',
        occurred_at: Date.now() / 1000, body: messageText(message).slice(0, 32000),
      }, false, undefined, payload.signal);
    } catch {
      prompts.delete(payload.agent.id);
      logger.warn('LE state unavailable');
    }
    return decision;
  });
  const service = Object.freeze({
    contractVersion: 1,
    // Trusted Host integration only. No HTTP/tool surface or identity parsed from prose.
    async ingestNative({ agentId, channel, botId, conversationId, senderId, sourceId,
      text, sceneKind = 'private', targeting = 'unknown', occurredAt }, signal) {
      for (const [key, value] of Object.entries({ agentId, channel, botId, conversationId, senderId, sourceId }))
        requiredText(value, key);
      if (!['private', 'group'].includes(sceneKind) || typeof text !== 'string' || text.length > 32000
        || !Number.isFinite(occurredAt) || !['bot-mention', 'bot-reply', 'other', 'unknown'].includes(targeting))
        throw Error('invalid_native_evidence');
      const agent = ctx.agents.get(agentId);
      if (!agent || disposed) throw Error('agent_unavailable');
      attach(agent);
      const signals = { 'bot-mention': ['native_bot_mention'], 'bot-reply': ['native_bot_reply'],
        other: ['native_other_target'], unknown: [] }[targeting];
      return state(agent, {
        event_id: sourceId, source_id: sourceId, producer: 'dsh-native',
        event_type: 'human_message', actor_role: 'human', actor_id: senderId,
        occurred_at: occurredAt, body: text, signals,
      }, true, { bot_id: botId, persona_id: agentId, adapter_id: 'dsh-im',
        platform: channel, scene_kind: sceneKind, scene_id: conversationId,
        account_id: senderId, instance_id: config.dataDir }, signal);
    },
    async snapshot(agentId, signal) {
      const agent = ctx.agents.get(agentId);
      if (!agent || disposed) throw Error('agent_unavailable');
      attach(agent);
      return state(agent, undefined, false, undefined, signal);
    },
    async sendText({ deliveryId, botId, targetId, text }, signal) {
      if (!config.proactiveEnabled || disposed) throw Error('proactive_disabled');
      for (const [key, value] of Object.entries({ deliveryId, botId, targetId })) requiredText(value, key);
      if (typeof text !== 'string' || !text.trim() || text.length > 32000) throw Error('invalid_text');
      if (!bridge?.send) throw Error('bridge_unavailable');
      const fingerprint = createHash('sha256').update(JSON.stringify([botId, targetId, text])).digest('hex');
      const existing = sends.get(deliveryId);
      if (existing) {
        if (existing.fingerprint !== fingerprint) throw Error('delivery_id_conflict');
        return existing.promise;
      }
      // Reserve before send; an exception is unknown, never an invitation to resend.
      const promise = Promise.resolve().then(async () => {
        if (signal?.aborted || disposed) return { status: 'canceled' };
        const reservation = await worker.call('reserve', { deliveryId, fingerprint }, signal);
        if (!reservation.reserved) return { status: reservation.status };
        let status = 'unknown';
        const controller = new AbortController();
        sendControllers.add(controller);
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        if (signal?.aborted || disposed) controller.abort();
        try {
          const result = await bridge.send(botId, targetId, text, { signal: controller.signal, format: 'text' });
          status = result?.sent === true ? 'accepted' : 'unknown';
        } catch { /* No automatic retry when a network write may have succeeded. */ }
        finally {
          signal?.removeEventListener('abort', abort);
          sendControllers.delete(controller);
        }
        await worker.call('delivered', { deliveryId, status }).catch(() => {});
        return { status };
      });
      sends.set(deliveryId, { fingerprint, promise });
      if (sends.size > 256) sends.delete(sends.keys().next().value);
      return promise;
    },
  });
  ctx.provide('livingEmotion', service);
  ctx.effect(() => () => {
    disposed = true;
    for (const controller of sendControllers) controller.abort();
    for (const item of agents.values()) item.dispose();
    agents.clear();
    prompts.clear();
    sends.clear();
  });
}
