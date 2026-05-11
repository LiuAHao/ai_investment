/**
 * 反馈控制组件
 */

import React, { useState } from 'react';
import {
  ThumbsUp,
  ThumbsDown,
  AlertTriangle,
  MessageSquare,
  Send,
} from 'lucide-react';
import { submitFeedback } from '../../services/apiV2Service';

const FEEDBACK_OPTIONS = [
  { type: 'useful', label: '有用', icon: ThumbsUp, activeClass: 'bg-green-100 text-green-600' },
  { type: 'inaccurate', label: '不准确', icon: ThumbsDown, activeClass: 'bg-red-100 text-red-600' },
  { type: 'risk_insufficient', label: '风险提示不足', icon: AlertTriangle, activeClass: 'bg-yellow-100 text-yellow-700' },
  { type: 'not_specific', label: '不够具体', icon: MessageSquare, activeClass: 'bg-blue-100 text-blue-600' },
];

const FeedbackControl = ({ sessionId }) => {
  const [selectedFeedback, setSelectedFeedback] = useState(null);
  const [comment, setComment] = useState('');
  const [showComment, setShowComment] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleFeedbackClick = async (type) => {
    if (submitted) return;

    setSelectedFeedback(type);

    if (type === 'useful') {
      await handleSubmit(type);
    } else {
      setShowComment(true);
    }
  };

  const handleSubmit = async (type, commentText = '') => {
    if (submitted || submitting) return;

    setSubmitting(true);
    try {
      if (!sessionId) {
        throw new Error('缺少会话信息');
      }
      await submitFeedback(sessionId, {
        feedback_type: type || selectedFeedback,
        comment: commentText || comment,
      });
      setSubmitted(true);
    } catch (error) {
      console.error('Submit feedback failed:', error);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="text-xs text-gray-400 flex items-center gap-1">
        <ThumbsUp className="w-3 h-3" />
        感谢反馈
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1">
        <span className="text-xs text-gray-400 mr-1">这个回答:</span>
        {FEEDBACK_OPTIONS.map((option) => {
          const Icon = option.icon;
          const isSelected = selectedFeedback === option.type;
          return (
            <button
              key={option.type}
              onClick={() => handleFeedbackClick(option.type)}
              disabled={submitting}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition ${
                isSelected
                  ? option.activeClass
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
              }`}
              title={option.label}
            >
              <Icon className="w-3 h-3" />
            </button>
          );
        })}
      </div>

      {showComment && (
        <div className="flex gap-2">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="补充说明（可选）..."
            className="flex-1 px-2 py-1 text-xs border rounded"
          />
          <button
            onClick={() => handleSubmit(null, comment)}
            disabled={submitting}
            className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            <Send className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
};

export default FeedbackControl;
