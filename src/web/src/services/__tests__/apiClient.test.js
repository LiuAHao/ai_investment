import { beforeEach, describe, expect, it } from 'vitest'

import { subscribeAgentEvents } from '../apiClient'

let instances = []

class FakeEventSource {
  constructor(url) {
    this.url = url
    this.listeners = {}
    this.closed = false
    instances.push(this)
  }

  addEventListener(name, handler) {
    if (!this.listeners[name]) this.listeners[name] = []
    this.listeners[name].push(handler)
  }

  close() {
    this.closed = true
  }
}

beforeEach(() => {
  instances = []
  globalThis.EventSource = FakeEventSource
})

describe('subscribeAgentEvents', () => {
  it('subscribes to all v4 pipeline events', () => {
    subscribeAgentEvents('task_1', () => {})
    const names = Object.keys(instances[0].listeners)
    const required = [
      'phase_started', 'phase_completed', 'evidence_added', 'thesis_submitted',
      'debate_turn', 'verdict_ready', 'verification_failed', 'decision_recorded',
      'plan_ready', 'final_answer', 'task_completed',
    ]
    required.forEach((name) => expect(names).toContain(name))
  })

  it('unwraps SSE frames into {type, data, timestamp}', () => {
    const received = []
    subscribeAgentEvents('task_1', (event) => received.push(event))
    const handler = instances[0].listeners['verdict_ready'][0]
    handler({
      data: JSON.stringify({
        type: 'verdict_ready',
        task_id: 'task_1',
        timestamp: 123,
        data: { stance: 'bullish', conviction: 0.7 },
      }),
    })
    expect(received).toHaveLength(1)
    expect(received[0].type).toBe('verdict_ready')
    expect(received[0].data.stance).toBe('bullish')
    expect(received[0].timestamp).toBe(123)
  })

  it('exposes close handle', () => {
    const handle = subscribeAgentEvents('task_1', () => {})
    handle.close()
    expect(instances[0].closed).toBe(true)
  })
})
