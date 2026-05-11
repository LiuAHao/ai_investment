/**
 * 评测面板组件
 * 显示评测结果和趋势
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  RefreshCw,
} from 'lucide-react';
import { getEvalRuns } from '../../services/apiV2Service';

const EvalDashboard = () => {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedRun, setSelectedRun] = useState(null);

  const loadEvalRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getEvalRuns();
      setRuns(data.runs || []);
    } catch (error) {
      console.error('Load eval runs failed:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadEvalRuns();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadEvalRuns]);

  const scoreColorClass = {
    green: 'bg-green-500',
    blue: 'bg-blue-500',
    purple: 'bg-purple-500',
  };

  const ScoreBar = ({ label, score, color = 'blue' }) => (
    <div className="mb-2">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="text-gray-800 font-medium">
          {(score * 100).toFixed(0)}%
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`${scoreColorClass[color] || scoreColorClass.blue} h-2 rounded-full transition-all`}
          style={{ width: `${Math.min(score * 100, 100)}%` }}
        />
      </div>
    </div>
  );

  return (
    <div className="p-4 overflow-auto h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">评测结果</h3>
        <button
          onClick={loadEvalRuns}
          disabled={loading}
          className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-400">加载中...</div>
      ) : runs.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          暂无评测记录
        </div>
      ) : (
        <div className="space-y-3">
          {runs.map((run) => (
            <div
              key={run.run_id}
              onClick={() => setSelectedRun(run)}
              className={`p-3 border rounded cursor-pointer hover:shadow transition ${
                selectedRun?.run_id === run.run_id
                  ? 'border-blue-300 bg-blue-50'
                  : ''
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-medium">
                    {run.dataset_name}
                  </span>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(run.created_at).toLocaleString('zh-CN')}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="text-center">
                  <div className="text-gray-500">通过率</div>
                  <div className="font-medium text-lg">
                    {((run.passed_cases / run.total_cases) * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-gray-500">平均分</div>
                  <div className="font-medium text-lg">
                    {(run.avg_score * 100).toFixed(0)}
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-gray-500">用例数</div>
                  <div className="font-medium text-lg">{run.total_cases}</div>
                </div>
              </div>

              {selectedRun?.run_id === run.run_id && run.summary_json && (
                <div className="mt-3 pt-3 border-t">
                  <ScoreBar
                    label="合规分"
                    score={run.summary_json.avg_compliance_score || 0}
                    color="green"
                  />
                  <ScoreBar
                    label="规则分"
                    score={run.summary_json.avg_rule_score || 0}
                    color="blue"
                  />
                  <ScoreBar
                    label="LLM分"
                    score={run.summary_json.avg_llm_score || 0}
                    color="purple"
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EvalDashboard;
