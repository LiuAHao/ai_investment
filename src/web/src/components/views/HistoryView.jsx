import React, { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowUpRight, History } from 'lucide-react'
import { getHistory, getSessionHistory } from '../../services/apiClient'
import { formatClock, formatSessionDay } from '../../utils/format'
import TurnDetail from '../agents/TurnDetail'

const HistoryView = ({ onBack }) => {
  const [sessions, setSessions] = useState([])
  const [active, setActive] = useState(null)
  const [turns, setTurns] = useState([])
  const [activeSession, setActiveSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const fetchSessions = async () => {
      try {
        const { sessions: list } = await getHistory()
        if (!cancelled) setSessions(list || [])
      } catch (e) {
        if (!cancelled) {
          setSessions([])
          setError(e.message || '无法加载历史会话')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchSessions()
    return () => { cancelled = true }
  }, [])

  const groups = useMemo(() => {
    const map = new Map()
    sessions.forEach((session) => {
      const day = formatSessionDay(session.updated_at)
      if (!map.has(day)) map.set(day, [])
      map.get(day).push(session)
    })
    return [...map.entries()]
  }, [sessions])

  const openSession = (session) => {
    setActive(session.session_id)
    setActiveSession(session)
    setTurns([])
    setDetailLoading(true)
    setError('')
  }

  useEffect(() => {
    if (!activeSession) return undefined
    let cancelled = false
    getSessionHistory(activeSession.session_id)
      .then(({ turns: list }) => {
        if (!cancelled) setTurns(list || [])
      })
      .catch((e) => {
        if (!cancelled) {
          setTurns([])
          setError(e.message || '无法加载会话详情')
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })
    return () => { cancelled = true }
  }, [activeSession])

  const backToList = () => {
    setActive(null)
    setActiveSession(null)
    setTurns([])
    setError('')
  }

  if (active) {
    return (
      <div>
        <div className="history-view-head">
          <button className="back-btn" onClick={backToList}>
            <ArrowLeft size={15} /> 返回列表
          </button>
          <h2>会话详情</h2>
        </div>
        {error && <div className="empty-state" style={{ color: 'var(--red)' }}>{error}</div>}
        {detailLoading && (
          <div className="skeleton-list">
            <div className="skeleton-row" />
            <div className="skeleton-row" />
          </div>
        )}
        {!detailLoading && !error && turns.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">空会话</div>
            该会话暂无记录
          </div>
        )}
        {!detailLoading && turns.map((turn, index) => (
          <TurnDetail key={index} turn={turn} />
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="history-view-head">
        <button className="back-btn" onClick={onBack}>
          <ArrowLeft size={15} /> 返回研究
        </button>
        <h2>历史记录</h2>
        {!loading && !error && <span className="history-count">{sessions.length} 段对话</span>}
      </div>

      {error && <div className="empty-state" style={{ color: 'var(--red)' }}>{error}</div>}

      {loading && (
        <div className="skeleton-list">
          <div className="skeleton-row" />
          <div className="skeleton-row" />
          <div className="skeleton-row" />
        </div>
      )}

      {!loading && !error && sessions.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-title">还没有研究记录</div>
          完成一次研究后，这里会自动保存，重启服务也不会丢失。
        </div>
      )}

      {!loading && groups.map(([day, items]) => (
        <section className="history-group" key={day}>
          <div className="history-group-title">{day}</div>
          <div className="history-list">
            {items.map((session) => (
              <button
                type="button"
                key={session.session_id}
                className="history-item"
                onClick={() => openSession(session)}
              >
                <History size={15} style={{ color: 'var(--text3)', flexShrink: 0 }} />
                <span className="history-main">
                  <span className="history-title">{session.title}</span>
                  <span className="history-meta">
                    {session.turn_count} 轮 · {formatClock(session.updated_at)}
                  </span>
                </span>
                <ArrowUpRight size={15} className="history-arrow" />
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

export default HistoryView
