import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { Context } from '@deepseek-ai/cordis';
import { AgentRegistry, agentEvents, assembleContextFor } from '@deepseek-ai/dsh-agent';
import { SystemPrompt } from '@deepseek-ai/dsh-system-prompt';
import { createScope } from '@deepseek-ai/dsh-scope';
import * as LE from '../../dsh/index.mjs';
import { WorkerClient } from '../../dsh/worker-client.mjs';

const message = (id, text, extra = []) => ({
  id, role: 'user', source: { kind: 'user' },
  content: [{ type: 'text', text }, ...extra],
});
async function fixture(t, config = {}, directory) {
  const dataDir = directory ?? await mkdtemp(path.join(os.tmpdir(), 'le-dsh-test-'));
  const ctx = new Context();
  const realNow = Date.now;
  Date.now = () => 1795401000000;
  t.after(() => { Date.now = realNow; });
  const registry = await ctx.plugin(AgentRegistry);
  const prompt = await ctx.plugin(SystemPrompt, {});
  const owner = ctx.plugin({ inject: ['agents', 'systemPrompt'], apply() {} });
  await owner.await();
  const bridge = ctx.provide('dshIm', { send: async () => ({ sent: true }) });
  const plugin = await ctx.plugin(LE, { dataDir, ...config });
  const scopes = [];
  t.after(async () => {
    await plugin.dispose();
    for (const scope of scopes) await scope.dispose();
    await owner.dispose();
    await bridge();
    await prompt.dispose();
    await registry.dispose();
    if (!directory) await rm(dataDir, { recursive: true, force: true });
  });
  await plugin.await();
  assert.equal(plugin.state, 2);
  const agent = async id => {
    const value = { id, session: { id } };
    const scope = createScope(owner.ctx, value);
    value.ctx = scope.ctx;
    scopes.push(scope);
    await ctx.agents.register(value);
    return value;
  };
  const step = (agent, messages, next = async () => ({ kind: 'enter', messages })) =>
    agentEvents(ctx, agent).waterfall('agent/pre-step', {
      messages, turn: 1, step: 1, signal: new AbortController().signal,
    }, next);
  return { ctx, plugin, agent, step, dataDir };
}

test('real Cordis lifecycle; concurrent sessions; prompt refresh; no inferred relationship', async t => {
  const f = await fixture(t);
  const a = await f.agent('a');
  const b = await f.agent('b');
  const accepted = [message('a-1', '你真棒')];
  const assembly = await f.ctx.systemPrompt.assemble(assembleContextFor(a));
  const results = await Promise.all([f.step(a, accepted), f.step(b, [message('b-1', '闭嘴')])]);
  assert.strictEqual(results[0].messages, accepted);
  const stateA = await f.ctx.livingEmotion.snapshot('a');
  const stateB = await f.ctx.livingEmotion.snapshot('b');
  assert.ok(stateA.affect.pleasure > stateB.affect.pleasure);
  assert.equal(stateA.relationship, null);
  const refreshed = f.ctx.systemPrompt.refreshContext(assembly, assembleContextFor(a));
  assert.ok(JSON.stringify(refreshed).includes('livingEmotion'));
  assert.ok(!JSON.stringify(await f.ctx.systemPrompt.assemble()).includes('livingEmotion'));
  const before = stateA.affect.pleasure;
  await f.step(a, accepted);
  assert.ok(Math.abs((await f.ctx.livingEmotion.snapshot('a')).affect.pleasure - before) < 0.001);
});

test('downstream rejection, internal messages and media preserve host semantics', async t => {
  const f = await fixture(t);
  const a = await f.agent('a');
  const rejected = { kind: 'reject' };
  assert.strictEqual(await f.step(a, [message('1', '闭嘴')], async () => rejected), rejected);
  assert.equal((await f.ctx.livingEmotion.snapshot('a')).affect.pleasure, 0);
  await f.step(a, [{ ...message('internal', '闭嘴'), source: { kind: 'model' } }]);
  assert.equal((await f.ctx.livingEmotion.snapshot('a')).affect.pleasure, 0);
  const media = [message('media', '你好', [{ type: 'image', image: { ref: 'synthetic' } }])];
  assert.strictEqual((await f.step(a, media)).messages, media);
});

test('native identity validates boundaries; group without targeting earns no relationship', async t => {
  const f = await fixture(t);
  await f.agent('a');
  const args = { agentId: 'a', channel: 'qq', botId: 'app', conversationId: 'group',
    senderId: 'user', sourceId: 'n1', text: '谢谢你', sceneKind: 'group',
    occurredAt: Date.now() / 1000 };
  const unknown = await f.ctx.livingEmotion.ingestNative(args);
  const targeted = await f.ctx.livingEmotion.ingestNative({
    ...args, sourceId: 'n2', targeting: 'bot-mention' });
  assert.ok(targeted.relationship.score > unknown.relationship.score);
  await assert.rejects(() => f.ctx.livingEmotion.ingestNative({ ...args, senderId: '' }));
  const b = await f.agent('b');
  assert.equal((await f.ctx.livingEmotion.snapshot(b.id)).relationship, null);
});

test('proactive accepted/unknown dedupe persists across reload; conflicts reject', async t => {
  const f = await fixture(t, { proactiveEnabled: true });
  let sends = 0;
  f.ctx.dshIm.send = async () => { sends++; throw Error('synthetic_network_failure'); };
  const args = { deliveryId: 'once', botId: 'app', targetId: 'registered-target', text: '你好' };
  assert.deepEqual(await f.ctx.livingEmotion.sendText(args), { status: 'unknown' });
  assert.deepEqual(await f.ctx.livingEmotion.sendText(args), { status: 'unknown' });
  assert.equal(sends, 1);
  await assert.rejects(() => f.ctx.livingEmotion.sendText({ ...args, text: '不同' }));
  await f.plugin.dispose();
  const reloaded = await f.ctx.plugin(LE, { dataDir: f.dataDir, proactiveEnabled: true });
  t.after(() => reloaded.dispose());
  await reloaded.await();
  assert.deepEqual(await f.ctx.livingEmotion.sendText(args), { status: 'unknown' });
  assert.equal(sends, 1);
  f.ctx.dshIm.send = async () => { sends++; return { sent: true }; };
  assert.deepEqual(await f.ctx.livingEmotion.sendText({ ...args, deliveryId: 'ok' }), { status: 'accepted' });
});

test('worker failure settles requests; stop leaves no child process', async t => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'le-worker-test-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const worker = new WorkerClient('python3', directory);
  await worker.call('ping');
  const pid = worker.child.pid;
  await worker.stop();
  assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' });
  await assert.rejects(() => worker.call('ping'));
  const missing = new WorkerClient('/nonexistent/python', directory);
  await assert.rejects(() => missing.call('ping'));
  await missing.stop();
});

test('emotion persistence survives reload of the plugin with a live Agent', async t => {
  const f = await fixture(t);
  const a = await f.agent('a');
  await f.step(a, [message('persistent', '你真棒')]);
  const before = await f.ctx.livingEmotion.snapshot('a');
  await f.plugin.dispose();
  const reloaded = f.ctx.plugin(LE, { dataDir: f.dataDir });
  t.after(() => reloaded.dispose());
  await reloaded.await();
  assert.deepEqual((await f.ctx.livingEmotion.snapshot('a')).affect, before.affect);
  await f.step(a, [message('persistent', '你真棒')]);
  assert.deepEqual((await f.ctx.livingEmotion.snapshot('a')).affect, before.affect);
});

test('plugin unload cancels an in-flight bridge send without retry', async t => {
  const f = await fixture(t, { proactiveEnabled: true });
  let start;
  const started = new Promise(resolve => { start = resolve; });
  let aborted = false;
  f.ctx.dshIm.send = async (_bot, _target, _text, { signal }) => {
    start();
    await new Promise(resolve => signal.addEventListener('abort', () => {
      aborted = true;
      resolve();
    }, { once: true }));
    throw Error('canceled_unknown');
  };
  const result = f.ctx.livingEmotion.sendText({
    deliveryId: 'cancel', botId: 'app', targetId: 'target', text: 'hello',
  });
  await started;
  await f.plugin.dispose();
  assert.equal(aborted, true);
  assert.deepEqual(await result, { status: 'unknown' });
});

test('schema and runtime validation agree; disabled starts no worker', async t => {
  assert.deepEqual(LE.normalizeConfig(LE.Config({ enabled: false })).enabled, false);
  assert.throws(() => LE.normalizeConfig({ proactiveEnabled: 'true' }));
  const f = await fixture(t, { enabled: false });
  assert.equal(f.ctx.livingEmotion, undefined);
});
