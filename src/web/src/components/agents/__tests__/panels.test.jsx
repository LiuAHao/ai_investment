import React from 'react'
import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import PhaseProgress from '../PhaseProgress'
import VerdictPanel from '../VerdictPanel'
import EvidencePanel from '../EvidencePanel'
import DebateTimeline from '../DebateTimeline'

describe('PhaseProgress', () => {
  it('renders explicit skipped phase and short durations', () => {
    render(
      <PhaseProgress
        phases={{
          L0: { status: 'done', duration_ms: 1200 },
          L1: { status: 'done', duration_ms: 5400, degraded: true },
          L3: { status: 'done', duration_ms: 20, detail: { skipped: true, reason: 'debate_disabled' } },
          L4: { status: 'done', duration_ms: 3000 },
          L6: { status: 'done', duration_ms: 1 },
        }}
      />,
    )
    expect(screen.getByText('L0')).toBeTruthy()
    expect(screen.getByText('L6')).toBeTruthy()
    expect(screen.getByText('未启用')).toBeTruthy()
    expect(screen.getAllByText('<0.1s').length).toBeGreaterThan(0)
    expect(screen.queryByText('跳过')).toBeNull()
  })

  it('marks insufficient theses separately', () => {
    render(
      <PhaseProgress
        phases={{ L3: { status: 'done', duration_ms: 5, detail: { skipped: true, reason: 'insufficient_theses' } } }}
      />,
    )
    expect(screen.getByText('论点不足')).toBeTruthy()
  })

  it('renders nothing without phase data', () => {
    const { container } = render(<PhaseProgress phases={{}} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('VerdictPanel', () => {
  const verdict = {
    stance: 'bearish',
    conviction: 0.63,
    blind_stance: 'neutral',
    blind_conviction: 0.55,
    revision_reason: '空方关于盈利转负的论据更强',
    key_drivers: ['营收增速降至近零（EV-0002）'],
    disagreement_map: [{
      topic: '估值是否已反映悲观预期',
      bull_view: '已反映，PE 低分位',
      bear_view: 'PB 仍高分位',
      resolvable: 'needs_data',
      resolution: '等待 Q3 报表',
    }],
    position_hint: '0%-10% 试探仓位',
    time_frame: '1-3 个月',
    falsifiers_to_watch: ['Q3 单季利润转正'],
    what_would_change_my_mind: ['毛利率回升至 90% 以上'],
    confidence_calibration: '最可能错在对增速持续性的假设',
  }

  it('renders blind vs final and decision details', () => {
    render(<VerdictPanel verdict={verdict} verification={{ passed: true, issues: [] }} />)

    expect(screen.getAllByText(/盲判/).length).toBeGreaterThan(0)
    expect(screen.getByText(/空方关于盈利转负的论据更强/)).toBeTruthy()
    expect(screen.getByText(/估值是否已反映悲观预期/)).toBeTruthy()
    expect(screen.getByText(/0%-10% 试探仓位/)).toBeTruthy()
    expect(screen.getByText(/Q3 单季利润转正/)).toBeTruthy()
    expect(screen.getByText(/最可能错在对增速持续性的假设/)).toBeTruthy()
    expect(screen.getAllByText((content, element) => element?.textContent === '质检：通过').length).toBeGreaterThan(0)
  })

  it('shows a placeholder while adjudicating', () => {
    render(<VerdictPanel verdict={null} active />)
    expect(screen.getByText(/裁决中/)).toBeTruthy()
    expect(screen.getByText(/先做盲判/)).toBeTruthy()
  })

  it('shows verification issues when failed', () => {
    render(
      <VerdictPanel
        verdict={{ ...verdict, stance: 'neutral' }}
        verification={{
          passed: false,
          issues: [{ kind: 'invalid_ref', detail: 'claim 引用了不存在的证据 EV-9999' }],
        }}
      />,
    )
    expect(screen.getByText(/质检未通过/)).toBeTruthy()
    expect(screen.getByText(/查看 1 条/)).toBeTruthy()
  })
})

describe('EvidencePanel', () => {
  const evidence = [
    { evidence_id: 'EV-0001', category: 'market', statement: '近 20 日涨幅 8.2%', value: 8.2, unit: '%', source_time: '2026-06-30', caliber: '前复权' },
    { evidence_id: 'EV-0002', category: 'fundamental', statement: '营收同比 12.5%', value: 12.5, unit: '%', source_time: '2026-04-28', caliber: '单季同比' },
  ]

  it('groups evidence and collapses market by default', () => {
    render(<EvidencePanel evidence={evidence} />)
    // 行情默认收起，财务默认展开
    expect(screen.queryByText('EV-0001')).toBeNull()
    expect(screen.getByText('EV-0002')).toBeTruthy()
    expect(screen.getByText(/行情 · 1/)).toBeTruthy()
    expect(screen.getByText(/财务 · 1/)).toBeTruthy()
    fireEvent.click(screen.getByText(/行情 · 1/))
    expect(screen.getByText('EV-0001')).toBeTruthy()
  })

  it('shows a collecting placeholder while active without evidence', () => {
    render(<EvidencePanel evidence={[]} active />)
    expect(screen.getByText(/正在采集证据/)).toBeTruthy()
  })

  it('renders nothing when inactive and empty', () => {
    const { container } = render(<EvidencePanel evidence={[]} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('DebateTimeline', () => {
  it('renders turns, concessions and thesis summary', () => {
    render(
      <DebateTimeline
        theses={{
          bull: { claim_count: 3, confidence: 0.7 },
          bear: { claims: [{ claim_id: 'C1' }, { claim_id: 'C2' }], confidence: 0.6 },
        }}
        turns={[
          { round: 1, side: 'bull', action: 'attack', attack_type: 'priced_in', target_claim_id: 'CLM-BEAR-01', argument: '估值未反映增长' },
          { round: 2, side: 'bear', action: 'concede', target_claim_id: 'CLM-BEAR-01', argument: '同意部分定价', concession: '撤回该论点' },
          { round: 2, side: 'bull', action: 'defend', argument: '本轮未让步', no_concession_reason: '证据仍支持' },
        ]}
      />,
    )
    expect(screen.getByText(/多方 3 条/)).toBeTruthy()
    expect(screen.getByText(/空方 2 条/)).toBeTruthy()
    expect(screen.getAllByText(/R1/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/R2/).length).toBeGreaterThan(0)
    expect(screen.getByText(/撤回该论点/)).toBeTruthy()
    expect(screen.getByText(/零让步说明/)).toBeTruthy()
  })

  it('renders a skipped placeholder when debate is disabled', () => {
    render(<DebateTimeline turns={[]} theses={{}} active skippedLabel="本次为宏观研究，未启用多空辩论。" />)
    expect(screen.getByText(/未启用多空辩论/)).toBeTruthy()
  })

  it('renders nothing without turns or theses', () => {
    const { container } = render(<DebateTimeline turns={[]} theses={{}} />)
    expect(container.firstChild).toBeNull()
  })
})
