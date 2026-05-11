/**
 * 工具轨迹面板组件
 */

import React from 'react';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  ChevronRight,
} from 'lucide-react';

const STATUS_CONFIG = {
  completed: { icon: CheckCircle2, color: 'text-green-500', label: '完成' },
  running: { icon: Loader2, color: 'text-blue-500', label: '运行中' },
  failed: { icon: XCircle, color: 'text-red-500', label: '失败' },
  pending: { icon: Clock, color: 'text-gray-400', label: '等待' },
};

const NODE_LABELS = {
  load_context: '加载上下文',
  route_intent: '意图识别',
  resolve_assets: '资产解析',
  plan_tasks: '任务规划',
  execute_tools: '执行工具',
  collect_evidence: '收集证据',
  draft_answer: '生成草稿',
  critic_check: '评审检查',
  compose_answer: '组装答案',
  compliance_check: '合规检查',
  finalize_answer: '最终化',
  save_memory: '保存记忆',
};

const ToolTracePanel = ({ trace, debugMode }) => {
  if (!trace || trace.length === 0) {
    return (
      <div className="p-4 text-center text-gray-400">
        暂无执行轨迹
      </div>
    );
  }

  return (
    <div className="overflow-auto h-full p-2">
      <div className="space-y-1">
        {trace.map((item, index) => {
          const statusConfig = STATUS_CONFIG[item.status] || STATUS_CONFIG.pending;
          const StatusIcon = statusConfig.icon;
          const label = NODE_LABELS[item.node] || item.node;

          return (
            <div
              key={index}
              className="flex items-center gap-2 p-2 rounded hover:bg-gray-50"
            >
              <StatusIcon
                className={`w-4 h-4 ${statusConfig.color} ${
                  item.status === 'running' ? 'animate-spin' : ''
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-gray-700">{label}</div>
                {debugMode && item.latency && (
                  <div className="text-xs text-gray-400">
                    {item.latency}ms
                  </div>
                )}
              </div>
              {index < trace.length - 1 && (
                <ChevronRight className="w-3 h-3 text-gray-300" />
              )}
            </div>
          );
        })}
      </div>

      {debugMode && (
        <div className="mt-4 p-3 bg-gray-50 rounded text-xs text-gray-500">
          <div className="font-medium mb-1">调试信息</div>
          <div>节点数: {trace.length}</div>
          <div>
            完成: {trace.filter(t => t.status === 'completed').length}
          </div>
          <div>
            运行中: {trace.filter(t => t.status === 'running').length}
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolTracePanel;
