import React, { useCallback, useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { getHistory, getSessionHistory } from '../../services/apiClient'
import TurnDetail from '../agents/TurnDetail'

const HistoryView = ({ onBack }) => {
  const [sessions, setSessions] = useState([])
  const [active, setActive] = useState(null)
  const [turns, setTurns] = useState([])
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { sessions } = await getHistory()
      setSessions(sessions || [])
    } catch {
      setSessions([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openSession = async (sessionId) => {
    setActive(sessionId)
    setDetailLoading(true)
    try {
      const { turns } = await getSessionHistory(sessionId)
      setTurns(turns || [])
    } catch {
      setTurns([])
    } finally {
      setDetailLoading(false)
    }
  }

  if (active) {
    return (
      <div>
        <div className="history-view-head">
          <button className="back-btn" onClick={() => { setActive(null); setTurns([]) }}>
            <ArrowLeft size={15} /> 返回列表
          </button>
          <h2>会话详情</h2>
        </div>
        {detailLoading && <div className="empty-state">加载中...</div>}
        {!detailLoading && turns.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">空会话</div>
            该会话暂无记录
          </div>
        )}
        {turns.map((turn, i) => (
          <TurnDetail key={i} turn={turn} />
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
      </div>
      {loading && <div className="empty-state">加载中...</div>}
      {!loading && sessions.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-title">暂无历史会话</div>
          （完成研究后自动保存，重启服务不丢失）
        </div>
      )}
      <div className="history-list">
        {sessions.map((s) => (
          <div key={s.session_id} className="history-item" onClick={() => openSession(s.session_id)}>
            <div className="history-title">{s.title}</div>
            <div className="history-meta">
              {s.turn_count} 轮 · {s.updated_at?.slice(0, 19).replace('T', ' ')}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default HistoryView
