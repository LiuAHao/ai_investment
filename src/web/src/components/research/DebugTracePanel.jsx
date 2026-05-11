/**
 * 调试轨迹面板组件
 * 显示完整的 Agent 执行过程
 */

import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
} from 'lucide-react';

const DebugSection = ({
  title,
  id,
  children,
  defaultOpen = false,
  expandedSections,
  onToggle,
}) => {
  const isExpanded = expandedSections[id] ?? defaultOpen;
  return (
    <div className="border rounded mb-2">
      <button
        onClick={() => onToggle(id)}
        className="w-full flex items-center gap-2 p-2 hover:bg-gray-50 text-left"
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
        <span className="text-sm font-medium">{title}</span>
      </button>
      {isExpanded && (
        <div className="p-2 border-t bg-gray-50 text-xs">
          {children}
        </div>
      )}
    </div>
  );
};

const DebugTracePanel = ({ trace, toolResults, evidence, investmentAnswer }) => {
  const [expandedSections, setExpandedSections] = useState({});
  const [copied, setCopied] = useState(false);

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const handleCopyAll = () => {
    const data = {
      trace,
      toolResults,
      evidence,
      investmentAnswer,
    };
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="p-4 overflow-auto h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">调试信息</h3>
        <button
          onClick={handleCopyAll}
          className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
        >
          {copied ? (
            <Check className="w-3 h-3 text-green-500" />
          ) : (
            <Copy className="w-3 h-3" />
          )}
          {copied ? '已复制' : '复制全部'}
        </button>
      </div>

      <DebugSection
        title="执行轨迹"
        id="trace"
        defaultOpen={true}
        expandedSections={expandedSections}
        onToggle={toggleSection}
      >
        {trace?.length > 0 ? (
          <pre className="whitespace-pre-wrap text-xs">
            {JSON.stringify(trace, null, 2)}
          </pre>
        ) : (
          <span className="text-gray-400">无数据</span>
        )}
      </DebugSection>

      <DebugSection
        title="工具结果"
        id="tools"
        expandedSections={expandedSections}
        onToggle={toggleSection}
      >
        {toolResults?.length > 0 ? (
          <pre className="whitespace-pre-wrap text-xs">
            {JSON.stringify(toolResults, null, 2)}
          </pre>
        ) : (
          <span className="text-gray-400">无数据</span>
        )}
      </DebugSection>

      <DebugSection
        title="证据列表"
        id="evidence"
        expandedSections={expandedSections}
        onToggle={toggleSection}
      >
        {evidence?.length > 0 ? (
          <pre className="whitespace-pre-wrap text-xs">
            {JSON.stringify(evidence, null, 2)}
          </pre>
        ) : (
          <span className="text-gray-400">无数据</span>
        )}
      </DebugSection>

      <DebugSection
        title="结构化答案"
        id="answer"
        expandedSections={expandedSections}
        onToggle={toggleSection}
      >
        {investmentAnswer ? (
          <pre className="whitespace-pre-wrap text-xs">
            {JSON.stringify(investmentAnswer, null, 2)}
          </pre>
        ) : (
          <span className="text-gray-400">无数据</span>
        )}
      </DebugSection>
    </div>
  );
};

export default DebugTracePanel;
