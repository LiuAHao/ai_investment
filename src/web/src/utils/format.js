const AGENT_META = {
  MarketAgent: { title: '市场行情', short: '市', role: '价格 · 趋势 · 量能', tone: 'market' },
  MarketAnalyst: { title: '市场行情', short: '市', role: '价格 · 趋势 · 量能', tone: 'market' },
  NewsAgent: { title: '事件舆情', short: '闻', role: '新闻 · 公告 · 情绪', tone: 'news' },
  NewsAnalyst: { title: '事件舆情', short: '闻', role: '新闻 · 公告 · 情绪', tone: 'news' },
  FundamentalAnalyst: { title: '财务基本面', short: '财', role: '盈利 · 估值 · 同业', tone: 'fund' },
  MacroAnalyst: { title: '宏观政策', short: '宏', role: '利率 · 政策 · 周期', tone: 'macro' },
  SummaryAgent: { title: '综合研报', short: '研', role: '汇总 · 裁决 · 成文', tone: 'summary' },
  OrchestratorAgent: { title: '研究主管', short: '主', role: '拆解问题 · 调度分析师', tone: 'orch' },
}

const DEFAULT_AGENT_META = { title: '研究分析师', short: '析', role: '独立取证', tone: 'market' }

export function agentMeta(name) {
  return AGENT_META[name] || DEFAULT_AGENT_META
}

export const TOOL_LABELS = {
  asset_resolve: '标的识别',
  asset_news_search: '新闻检索',
  web_research: '联网调研',
  cn_stock_history: 'A 股行情',
  hk_stock_history: '港股行情',
  us_stock_history: '美股行情',
  stock_financial_summary: '财务摘要',
  stock_financial_indicator: '财务指标',
  stock_peer_compare: '同业对比',
  fund_profile: '基金概况',
  fund_nav_history: '基金净值',
  etf_profile: 'ETF 概况',
  etf_tracking_index: '跟踪指数',
  stock_fund_flow: '资金流向',
  stock_expectation: '预期数据',
  stock_valuation_band: '估值区间',
  stock_events: '公司事件',
  industry_context: '行业环境',
  macro_indicator: '宏观指标',
  index_environment: '指数环境',
}

export function toolLabel(name) {
  if (!name) return '数据工具'
  return TOOL_LABELS[name] || String(name).replace(/_/g, ' ')
}

const HORIZON_LABEL = {
  short: '短期',
  medium: '中期',
  long: '长期',
}

const HORIZON_RANGE = {
  short: '1–4 周',
  medium: '1–6 个月',
  long: '6 个月以上',
}

export function localizeHorizon(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  const match = text.match(/^(short|medium|long)\b[\s，,、·.。:：-]*([^（(]*)[（(]?([^）)]*)[）)]?$/i)
  if (match) {
    const key = match[1].toLowerCase()
    const extra = (match[2] || '').trim()
    if (extra) return `${HORIZON_LABEL[key]} · ${extra}`
    return `${HORIZON_LABEL[key]} · ${HORIZON_RANGE[key]}`
  }
  return HORIZON_LABEL[text.toLowerCase()] || text
}

export function formatDuration(ms) {
  if (ms === null || ms === undefined) return ''
  if (ms < 100) return '<0.1s'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatDateTime(value, withTime = true) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 19).replace('T', ' ')
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    ...(withTime ? { hour: '2-digit', minute: '2-digit', hour12: false } : {}),
  })
}

export function formatSessionDay(value) {
  if (!value) return '更早'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '更早'
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  const sameDay = (a, b) => a.toDateString() === b.toDateString()
  if (sameDay(date, today)) return '今天'
  if (sameDay(date, yesterday)) return '昨天'
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

export function formatClock(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(11, 16)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

export function isEvidenceRef(value) {
  return /(EV-\d{3,})/i.test(String(value || ''))
}

export function cleanSource(value) {
  const text = String(value || '').trim()
  if (!text || isEvidenceRef(text)) return ''
  return text
}
