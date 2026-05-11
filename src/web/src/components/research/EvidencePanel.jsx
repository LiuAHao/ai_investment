/**
 * 证据面板组件
 */

import React from 'react';
import {
  TrendingUp,
  Newspaper,
  BookOpen,
  BarChart3,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';

const EVIDENCE_TYPE_CONFIG = {
  market_data: { icon: TrendingUp, label: '行情', iconClass: 'text-blue-500' },
  news: { icon: Newspaper, label: '新闻', iconClass: 'text-green-500' },
  rag_knowledge: { icon: BookOpen, label: '知识', iconClass: 'text-purple-500' },
  technical_indicator: { icon: BarChart3, label: '技术', iconClass: 'text-orange-500' },
  fundamental: { icon: BarChart3, label: '基本面', iconClass: 'text-indigo-500' },
  macro: { icon: BarChart3, label: '宏观', iconClass: 'text-gray-500' },
};

const POLARITY_CONFIG = {
  positive: { icon: CheckCircle2, color: 'text-green-500', label: '利好' },
  negative: { icon: XCircle, color: 'text-red-500', label: '利空' },
  neutral: { icon: AlertTriangle, color: 'text-gray-500', label: '中性' },
};

const EvidencePanel = ({ evidence, debugMode }) => {
  if (!evidence || evidence.length === 0) {
    return (
      <div className="p-4 text-center text-gray-400">
        暂无证据数据
      </div>
    );
  }

  return (
    <div className="overflow-auto h-full">
      {evidence.map((item, index) => {
        const typeConfig = EVIDENCE_TYPE_CONFIG[item.evidence_type] || {
          icon: AlertTriangle,
          label: '其他',
          iconClass: 'text-gray-500',
        };
        const TypeIcon = typeConfig.icon;
        const polarity = POLARITY_CONFIG[item.polarity];
        const PolarityIcon = polarity?.icon;

        return (
          <div key={index} className="p-3 border-b hover:bg-gray-50">
            <div className="flex items-start gap-2">
              <TypeIcon className={`w-4 h-4 mt-1 ${typeConfig.iconClass}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-800 truncate">
                    {item.title || typeConfig.label}
                  </span>
                  {PolarityIcon && (
                    <PolarityIcon className={`w-3 h-3 ${polarity.color}`} />
                  )}
                </div>

                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                  {item.summary || '无摘要'}
                </p>

                <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                  {item.source && (
                    <span className="bg-gray-100 px-2 py-0.5 rounded">
                      {item.source}
                    </span>
                  )}
                  {item.confidence && (
                    <span>
                      置信度: {(item.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>

                {debugMode && item.limitations?.length > 0 && (
                  <div className="mt-2 text-xs text-yellow-600 bg-yellow-50 p-2 rounded">
                    <AlertTriangle className="w-3 h-3 inline mr-1" />
                    {item.limitations[0]}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default EvidencePanel;
