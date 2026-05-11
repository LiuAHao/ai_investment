/**
 * 会话列表组件
 */

import React, { useState, useEffect, useCallback } from 'react';
import { MessageSquare, Plus, Clock } from 'lucide-react';

const SessionList = ({ currentSession, onSessionSelect }) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/chat/sessions', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setSessions(data.sessions || []);
      }
    } catch (error) {
      console.error('Load sessions failed:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadSessions();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadSessions]);

  const handleNewSession = () => {
    onSessionSelect(null);
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-3 border-b">
        <button
          onClick={handleNewSession}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition"
        >
          <Plus className="w-4 h-4" />
          新研究
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="p-4 text-center text-gray-400">加载中...</div>
        ) : sessions.length === 0 ? (
          <div className="p-4 text-center text-gray-400">
            暂无会话记录
          </div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.session_id}
              onClick={() => onSessionSelect({ sessionId: session.session_id })}
              className={`p-3 border-b cursor-pointer hover:bg-gray-50 transition ${
                currentSession?.sessionId === session.session_id
                  ? 'bg-blue-50 border-l-2 border-l-blue-500'
                  : ''
              }`}
            >
              <div className="flex items-start gap-2">
                <MessageSquare className="w-4 h-4 mt-1 text-gray-400" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {session.query || '未命名会话'}
                  </div>
                  <div className="flex items-center gap-1 mt-1 text-xs text-gray-400">
                    <Clock className="w-3 h-3" />
                    <span>{formatTime(session.created_at)}</span>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default SessionList;
