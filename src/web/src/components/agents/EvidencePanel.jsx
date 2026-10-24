import React, { useMemo, useState } from 'react'
import { ChevronDown, ClipboardList } from 'lucide-react'

const CATEGORY_LABEL = {
  market: '行情',
  valuation: '估值',
  technical: '技术',
  fundamental: '财务',
  news: '新闻',
  announcement: '公告',
  macro: '宏观',
  policy: '政策',
  flow: '资金',
}

const PREVIEW_LEN = 120
const GROUP_PREVIEW = 8
const DEFAULT_COLLAPSED = new Set(['market', 'macro', 'news'])

const formatTime = (value) => {
  const text = String(value || '')
  if (/^\d{8}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6)}`
  return text
}

const valueBadge = (item) => {
  const raw = item.value
  if (raw === null || raw === undefined || raw === '') return null
  const num = Number(raw)
  if (Number.isNaN(num)) {
    return <span className="evidence-value">{String(raw).slice(0, 30)}</span>
  }
  const unit = item.unit || ''
  const isPct = unit.includes('%')
  const text = `${isPct && num > 0 ? '+' : ''}${Number.isInteger(num) ? num : num.toFixed(2)}${unit}`
  const tone = isPct ? (num > 0 ? 'is-up' : (num < 0 ? 'is-down' : '')) : ''
  return <span className={`evidence-value ${tone}`.trim()}>{text}</span>
}

/**
 * 证据台账：按类别分组，行情/宏观/新闻默认收起；来源细节收进元信息行。
 */
const EvidencePanel = ({ evidence = [], active = false }) => {
  const [open, setOpen] = useState(true)
  const [expandedGroups, setExpandedGroups] = useState({})
  const [showAll, setShowAll] = useState({})
  const [expandedItems, setExpandedItems] = useState({})

  // 工具原始数据包不进入台账阅读区：既没有可读事实，也会淹没真正的证据。
  const visibleEvidence = useMemo(() => evidence.filter((item) => {
    const statement = String(item.statement || '').trim()
    if (!statement) return false
    if (item.value !== null && item.value !== undefined && item.value !== '') return true
    return !(/返回数据$/.test(statement) || /^(无数据|暂无数据)$/.test(statement))
  }), [evidence])

  const groups = useMemo(() => {
    const map = {}
    visibleEvidence.forEach((item) => {
      const category = item.category || 'market'
      if (!map[category]) map[category] = []
      map[category].push(item)
    })
    return map
  }, [visibleEvidence])

  if (!visibleEvidence.length) {
    if (!active) return null
    return (
      <section className="card">
        <header className="card-head">
          <div className="card-avatar av-fund"><ClipboardList size={16} /></div>
          <div className="card-name">
            证据台账
            <small>数据收集中</small>
          </div>
        </header>
        <div className="card-body" style={{ fontSize: 12, color: 'var(--text3)' }}>
          {evidence.length
            ? '本轮回传的多为原始数据包，暂无可读的结构化证据。'
            : '正在采集证据… 工具每返回一条数据，这里会实时登记。'}
        </div>
      </section>
    )
  }

  return (
    <section className="card">
      <header className="card-head">
        <div className="card-avatar av-fund"><ClipboardList size={16} /></div>
        <div className="card-name">
          证据台账
          <small>{visibleEvidence.length} 条 · {Object.keys(groups).length} 类</small>
        </div>
        <button type="button" className="disclosure" onClick={() => setOpen((value) => !value)}>
          {open ? '收起' : '展开'}
          <ChevronDown size={13} style={{ transform: open ? 'rotate(180deg)' : 'none' }} />
        </button>
      </header>

      {open && (
        <div className="evidence-body">
          {Object.entries(groups).map(([category, items], groupIndex) => {
            const isExpanded = expandedGroups[category] ?? !DEFAULT_COLLAPSED.has(category)
            const visible = showAll[category] ? items : items.slice(0, GROUP_PREVIEW)
            return (
              <div key={category} className="evidence-group">
                <button
                  type="button"
                  className={`evidence-group-head ${isExpanded ? 'is-open' : ''}`}
                  onClick={() => setExpandedGroups((prev) => ({ ...prev, [category]: !isExpanded }))}
                  aria-expanded={isExpanded}
                >
                  {CATEGORY_LABEL[category] || category} · {items.length}
                  <ChevronDown size={12} />
                </button>

                {isExpanded && visible.map((item, itemIndex) => {
                  const id = item.evidence_id || ''
                  const text = item.statement || ''
                  const isLong = text.length > PREVIEW_LEN
                  const shown = expandedItems[id] || !isLong ? text : `${text.slice(0, PREVIEW_LEN)}…`
                  const meta = [
                    item.source_time ? `数据时间 ${formatTime(item.source_time)}` : '',
                    item.caliber || '',
                    item.seen_count > 1 ? `${item.seen_count} 个来源` : '',
                  ].filter(Boolean)

                  return (
                    <div key={id || `${category}-${itemIndex}`} className="evidence-row" title={item.source_tool || ''}>
                      <div className="evidence-line">
                        <span className="evidence-id">{id || '—'}</span>
                        <span className="evidence-text">{shown}</span>
                        {valueBadge(item)}
                      </div>
                      {(meta.length > 0 || item.conflict) && (
                        <div className="evidence-meta">
                          {meta.map((entry) => <span key={entry}>{entry}</span>)}
                          {item.conflict && <span className="evidence-conflict">数据晚于决策时点</span>}
                        </div>
                      )}
                      {isLong && (
                        <button
                          type="button"
                          className="evidence-more"
                          onClick={() => setExpandedItems((prev) => ({ ...prev, [id]: !prev[id] }))}
                        >
                          {expandedItems[id] ? '收起' : '展开全文'}
                        </button>
                      )}
                    </div>
                  )
                })}

                {isExpanded && items.length > GROUP_PREVIEW && (
                  <button
                    type="button"
                    className="evidence-more"
                    onClick={() => setShowAll((prev) => ({ ...prev, [category]: !prev[category] }))}
                  >
                    {showAll[category] ? '收起' : `展开其余 ${items.length - GROUP_PREVIEW} 条`}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

export default EvidencePanel
