/**
 * V2 研究工作台 - 流程画布设计
 * 匹配 index.html V2 原型的可视化流程
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { submitQuery, createEventStream, getTaskStatus } from '../../services/apiV2Service';

/* ── 常量定义 ── */
const AGENTS = [
  { id: 'context_loader', name: 'ContextLoader', desc: '加载会话上下文', phase: 0 },
  { id: 'router', name: 'RouterAgent', desc: '识别意图与资产', phase: 0 },
  { id: 'asset_resolver', name: 'AssetResolver', desc: '解析资产信息', phase: 0 },
  { id: 'planner', name: 'PlannerAgent', desc: '动态规划分析任务', phase: 1 },
  { id: 'tool_executor', name: 'ToolExecutor', desc: '并行执行工具调用', phase: 2 },
  { id: 'evidence_agent', name: 'EvidenceAgent', desc: '整理证据池', phase: 3 },
  { id: 'answer_draft', name: 'AnswerDraftAgent', desc: '生成分析草稿', phase: 4 },
  { id: 'critic', name: 'CriticAgent', desc: '事实与逻辑校验', phase: 4 },
  { id: 'compliance', name: 'ComplianceAgent', desc: '合规校验', phase: 4 },
  { id: 'answer_composer', name: 'AnswerComposer', desc: '生成最终结论', phase: 5 },
];

const PHASES = [
  { id: 0, title: '问题理解', desc: 'ContextLoader → RouterAgent → AssetResolver' },
  { id: 1, title: '动态规划', desc: 'PlannerAgent' },
  { id: 2, title: '并行工具执行', desc: '多工具同时运行' },
  { id: 3, title: '证据汇总', desc: 'EvidenceAgent' },
  { id: 4, title: '生成与校验', desc: 'AnswerDraftAgent → CriticAgent → ComplianceAgent' },
  { id: 5, title: '最终结论', desc: 'AnswerComposer' },
];

const RECOMMENDED_QUESTIONS = [
  '分析宁德时代未来三个月的风险',
  '沪深300ETF适合长期定投吗',
  'AAPL 当前估值贵不贵',
  '半导体行业近期有哪些风险',
];

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

function defaultAgentState() {
  const r = {};
  AGENTS.forEach(a => { r[a.id] = { status: 'pending', duration: null, logs: [] }; });
  return r;
}

/* ── 主组件 ── */
const ResearchChatView = () => {
  const [phase, setPhase] = useState('hero'); // hero | analyzing | done
  const [query, setQuery] = useState('');
  const [riskPref, setRiskPref] = useState('稳健型');
  const [period, setPeriod] = useState('三个月');
  const [debugMode, setDebugMode] = useState(false);

  // 分析状态
  const [turns, setTurns] = useState([]);
  const [activePhase, setActivePhase] = useState(-1);
  const [activeAgents, setActiveAgents] = useState(defaultAgentState);
  const [activeEvidence, setActiveEvidence] = useState([]);
  const [activeCritic, setActiveCritic] = useState(null);
  const [activeCompliance, setActiveCompliance] = useState(null);
  const [activeAnswer, setActiveAnswer] = useState(null);
  const [activeQuery, setActiveQuery] = useState('');
  const [activeTools, setActiveTools] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [expandedTurns, setExpandedTurns] = useState({});

  const eventStreamRef = useRef(null);
  const pollTimerRef = useRef(null);

  useEffect(() => {
    return () => {
      eventStreamRef.current?.close();
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  /* ── 工具函数 ── */
  const mapNodeToAgent = useCallback((nodeName) => {
    const mapping = {
      load_context: 'context_loader',
      route_intent: 'router',
      resolve_assets: 'asset_resolver',
      plan_tasks: 'planner',
      execute_tools: 'tool_executor',
      collect_evidence: 'evidence_agent',
      draft_answer: 'answer_draft',
      critic_check: 'critic',
      compliance_check: 'compliance',
      compose_answer: 'answer_composer',
      finalize_answer: 'answer_composer',
      save_memory: 'answer_composer',
    };
    return mapping[nodeName] || nodeName;
  }, []);

  const mapNodeToPhase = useCallback((nodeName) => {
    const mapping = {
      load_context: 0, route_intent: 0, resolve_assets: 0,
      plan_tasks: 1,
      execute_tools: 2,
      collect_evidence: 3,
      draft_answer: 4, critic_check: 4, compliance_check: 4,
      compose_answer: 5, finalize_answer: 5, save_memory: 5,
    };
    return mapping[nodeName] ?? -1;
  }, []);

  const applyCompletedResult = useCallback((result) => {
    setActivePhase(5);
    setActiveAnswer(result.investment_answer || result.answer || null);
    if (result.evidence_items) setActiveEvidence(result.evidence_items);
    if (result.critic_result) setActiveCritic(result.critic_result);
    if (result.compliance_result) setActiveCompliance(result.compliance_result);

    setActiveAgents(prev => {
      const updated = { ...prev };
      Object.keys(updated).forEach(k => {
        if (updated[k].status === 'running') {
          updated[k] = { ...updated[k], status: 'completed' };
        }
      });
      return updated;
    });

    setTurns(prev => {
      const newTurn = {
        id: `turn_${prev.length + 1}`,
        query: activeQuery,
        queryType: prev.length === 0 ? 'initial' : 'follow_up',
        agents: { ...activeAgents },
        tools: [...activeTools],
        evidenceItems: [...activeEvidence],
        criticResult: activeCritic,
        complianceResult: activeCompliance,
        answer: result.investment_answer || result.answer || null,
        createdAt: new Date().toLocaleString('zh-CN'),
      };
      return [...prev, newTurn];
    });

    setPhase('done');
  }, [activeQuery, activeAgents, activeTools, activeEvidence, activeCritic, activeCompliance]);

  /* ── SSE 事件处理 ── */
  const handleEvent = useCallback((event) => {
    switch (event.type) {
      case 'node_started': {
        const agentId = mapNodeToAgent(event.data?.node);
        const p = mapNodeToPhase(event.data?.node);
        setActivePhase(p);
        setActiveAgents(prev => ({
          ...prev,
          [agentId]: { ...prev[agentId], status: 'running' },
        }));
        break;
      }
      case 'node_completed': {
        const agentId = mapNodeToAgent(event.data?.node);
        setActiveAgents(prev => ({
          ...prev,
          [agentId]: {
            ...prev[agentId],
            status: 'completed',
            duration: event.data?.latency_ms,
          },
        }));
        break;
      }
      case 'tool_started': {
        setActiveTools(prev => [...prev, {
          name: event.data?.tool_name || 'unknown',
          status: 'running',
          desc: event.data?.description || '',
          logs: [],
          result: null,
        }]);
        break;
      }
      case 'tool_completed': {
        setActiveTools(prev => prev.map(t =>
          t.name === event.data?.tool_name
            ? { ...t, status: 'completed', result: event.data?.result }
            : t
        ));
        break;
      }
      case 'evidence_added': {
        if (event.data?.evidence) {
          setActiveEvidence(prev => [...prev, event.data.evidence]);
        }
        break;
      }
      case 'critic_completed': {
        setActiveCritic(event.data);
        break;
      }
      case 'compliance_completed': {
        setActiveCompliance(event.data);
        break;
      }
      case 'draft_created': {
        setActiveAnswer(event.data);
        break;
      }
      case 'task_completed': {
        applyCompletedResult(event.data?.result || {});
        break;
      }
      case 'task_failed': {
        setPhase('done');
        break;
      }
      default:
        break;
    }
  }, [mapNodeToAgent, mapNodeToPhase, applyCompletedResult]);

  /* ── 轮询 ── */
  const startPolling = useCallback((taskId) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    pollTimerRef.current = setInterval(async () => {
      try {
        const status = await getTaskStatus(taskId);
        if (status.status === 'completed') {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
          eventStreamRef.current?.close();
          applyCompletedResult(status.result || {});
        }
        if (['failed', 'timeout'].includes(status.status)) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
          eventStreamRef.current?.close();
          setPhase('done');
        }
      } catch {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
        setPhase('done');
      }
    }, 1200);
  }, [applyCompletedResult]);

  /* ── 提交分析 ── */
  const startAnalysis = async (q) => {
    const queryText = q || query;
    if (!queryText.trim()) return;

    setPhase('analyzing');
    setActiveQuery(queryText);
    setActivePhase(-1);
    setActiveAgents(defaultAgentState());
    setActiveEvidence([]);
    setActiveCritic(null);
    setActiveCompliance(null);
    setActiveAnswer(null);
    setActiveTools([]);

    try {
      const result = await submitQuery(queryText, currentSessionId, { debugMode, riskPref, period });
      if (result.task_id) {
        if (result.session_id) setCurrentSessionId(result.session_id);
        const stream = createEventStream(result.task_id, handleEvent, () => {
          startPolling(result.task_id);
        });
        eventStreamRef.current = stream;
        startPolling(result.task_id);
      }
    } catch {
      setPhase('done');
    }
  };

  const handleFollowUp = () => {
    if (!query.trim()) return;
    startAnalysis(query);
    setQuery('');
  };

  /* ── 渲染: 研究首页 ── */
  if (phase === 'hero') {
    return (
      <div style={{ maxWidth: 720, margin: '0 auto', padding: '48px 0', textAlign: 'center' }}>
        <h1 style={{ fontSize: 'clamp(28px, 4vw, 40px)', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 32 }}>
          你想研究什么？
        </h1>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); startAnalysis(); } }}
          placeholder="输入你想研究的投资问题, 例如: 分析宁德时代未来三个月的风险"
          style={{
            width: '100%', minHeight: 120, padding: '16px 20px',
            background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 12, color: 'var(--text)', fontSize: 16, lineHeight: 1.6, resize: 'vertical',
          }}
        />

        {/* Options bar */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, justifyContent: 'center', margin: '20px 0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13, color: 'var(--text3)' }}>风险偏好</span>
            <select value={riskPref} onChange={e => setRiskPref(e.target.value)} style={{ padding: '8px 32px 8px 12px', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
              {['保守型', '稳健型', '平衡型', '进取型', '激进型'].map(v => <option key={v}>{v}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13, color: 'var(--text3)' }}>投资周期</span>
            <select value={period} onChange={e => setPeriod(e.target.value)} style={{ padding: '8px 32px 8px 12px', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
              {['一个月', '三个月', '半年', '一年'].map(v => <option key={v}>{v}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13, color: 'var(--text3)' }}>调试模式</span>
            <button className={`toggle ${debugMode ? 'on' : ''}`} onClick={() => setDebugMode(!debugMode)}>
              <div className="toggle-knob" />
            </button>
          </div>
        </div>

        {/* Analyze button */}
        <div style={{ marginBottom: 32, textAlign: 'center' }}>
          <button
            onClick={() => startAnalysis()}
            style={{
              padding: '14px 48px', borderRadius: 8, fontSize: 16, fontWeight: 700,
              background: 'linear-gradient(135deg, var(--red), var(--orange))', color: '#fff',
              letterSpacing: '-0.01em',
            }}
          >
            开始分析
          </button>
        </div>

        {/* Recommended questions */}
        <div style={{ marginBottom: 8, textAlign: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--text3)', display: 'block', marginBottom: 10 }}>推荐问题</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
            {RECOMMENDED_QUESTIONS.map((q, i) => (
              <button
                key={i}
                onClick={() => setQuery(q)}
                style={{
                  padding: '6px 14px', borderRadius: 6, fontSize: 13,
                  background: 'rgba(220, 38, 38, 0.08)', color: 'var(--text2)',
                  border: '1px solid rgba(220, 38, 38, 0.15)',
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  /* ── 渲染: 流程画布 ── */
  const renderFlowCanvas = (turn, idx, isActive) => {
    const agents = isActive ? activeAgents : (turn.agents || defaultAgentState());
    const evidence = isActive ? activeEvidence : (turn.evidenceItems || []);
    const critic = isActive ? activeCritic : (turn.criticResult || null);
    const compliance = isActive ? activeCompliance : (turn.complianceResult || null);
    const answer = isActive ? activeAnswer : (turn.answer || null);
    const currentP = isActive ? activePhase : 5;

    return (
      <div key={turn.id || 'active'} style={{ animation: 'fadeIn 0.4s ease both' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <span style={{
            fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
            color: 'var(--red)', background: 'rgba(220, 38, 38, 0.1)', borderRadius: 4, padding: '2px 10px',
          }}>
            {turn.queryType === 'initial' ? '主问题' : `追问 ${idx}`}
          </span>
          <h2 style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1.4, flex: 1 }}>
            {turn.query}
          </h2>
          <span style={{ fontSize: 12, color: 'var(--text3)', fontFamily: 'ui-monospace, monospace' }}>
            {turn.createdAt}
          </span>
        </div>

        {/* Phase blocks */}
        {PHASES.map(p => {
          const pAgents = AGENTS.filter(a => a.phase === p.id);
          let phaseStatus = 'pending';
          if (p.id < currentP) phaseStatus = 'completed';
          else if (p.id === currentP) phaseStatus = 'running';

          return (
            <div key={p.id} className={`phase-block ${phaseStatus}`}>
              {/* Phase header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <div style={{
                  fontSize: 11, fontFamily: 'ui-monospace, monospace', fontWeight: 700,
                  color: phaseStatus === 'running' ? '#fff' : 'var(--red)',
                  background: phaseStatus === 'running' ? 'var(--red)' : 'rgba(220, 38, 38, 0.1)',
                  width: 28, height: 28, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {String(p.id + 1).padStart(2, '0')}
                </div>
                <span style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>{p.title}</span>
                <span style={{
                  fontSize: 12, fontWeight: 500, padding: '2px 8px', borderRadius: 4,
                  color: phaseStatus === 'running' ? 'var(--red)' : phaseStatus === 'completed' ? 'var(--green)' : 'var(--text3)',
                  background: phaseStatus === 'running' ? 'rgba(220,38,38,0.1)' : phaseStatus === 'completed' ? 'rgba(34,197,94,0.1)' : 'rgba(100,116,139,0.1)',
                }}>
                  {phaseStatus === 'running' ? '运行中' : phaseStatus === 'completed' ? '已完成' : '等待'}
                </span>
              </div>

              {/* Agent nodes or tool cards */}
              {p.id === 2 ? renderToolCards(isActive) : renderSerialAgents(pAgents, agents)}
            </div>
          );
        })}

        {/* Evidence panel */}
        {evidence.length > 0 && renderEvidencePanel(evidence)}

        {/* Validation panel */}
        {(critic || compliance) && renderValidationPanel(critic, compliance)}

        {/* Report */}
        {answer && renderReport(answer)}

        {/* Collapse button for completed turns */}
        {!isActive && (
          <button
            onClick={() => setExpandedTurns(prev => ({ ...prev, [turn.id]: !prev[turn.id] }))}
            style={{ fontSize: 13, color: 'var(--text3)', background: 'transparent', padding: '6px 0', marginBottom: 16, borderBottom: '1px dashed var(--border)', display: 'block', cursor: 'pointer' }}
          >
            折叠流程 ▴
          </button>
        )}
      </div>
    );
  };

  /* ── 串行 Agent 节点 ── */
  const renderSerialAgents = (phaseAgents, allAgents) => (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      {phaseAgents.map((agent, i) => {
        const aState = allAgents[agent.id] || { status: 'pending', duration: null, logs: [] };
        const aStatus = aState.status;
        return (
          <React.Fragment key={agent.id}>
            {i > 0 && <div style={{ display: 'flex', alignItems: 'center', color: 'var(--text3)', fontSize: 16, flexShrink: 0, alignSelf: 'center' }}>→</div>}
            <div className={`serial-agent ${aStatus}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                  background: aStatus === 'running' ? 'var(--red)' : aStatus === 'completed' ? 'var(--green)' : 'var(--card2)',
                  border: aStatus === 'pending' ? '1px solid var(--border)' : 'none',
                  animation: aStatus === 'running' ? 'breathe 1.5s ease-in-out infinite' : 'none',
                }} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>{agent.name}</span>
                <span style={{
                  fontSize: 11, marginLeft: 'auto',
                  color: aStatus === 'running' ? 'var(--red)' : aStatus === 'completed' ? 'var(--green)' : 'var(--text3)',
                }}>
                  {aStatus === 'running' ? '运行中' : aStatus === 'completed' ? '已完成' : '等待'}
                </span>
                {aState.duration && (
                  <span style={{ fontSize: 11, fontFamily: 'ui-monospace, monospace', color: 'var(--text3)', marginLeft: 4 }}>
                    {aState.duration}ms
                  </span>
                )}
              </div>
              <span style={{ fontSize: 12, color: 'var(--text3)' }}>{agent.desc}</span>
              {aState.logs && aState.logs.length > 0 && (
                <div style={{ marginTop: 8, maxHeight: 120, overflowY: 'auto' }}>
                  {aState.logs.map((log, li) => (
                    <div
                      key={li}
                      className={`agent-log-line ${li === aState.logs.length - 1 && aStatus === 'completed' ? 'done' : ''}`}
                      style={{ animationDelay: `${li * 0.08}s` }}
                    >
                      {log}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );

  /* ── 并行工具卡片 ── */
  const renderToolCards = (isActive) => {
    const tools = isActive ? activeTools : [];
    if (tools.length === 0) {
      return <div style={{ fontSize: 13, color: 'var(--text3)', padding: '8px 0' }}>等待工具执行...</div>;
    }
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
        {tools.map((tool, i) => (
          <div key={i} className={`tool-card ${tool.status}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'ui-monospace, monospace', flex: 1 }}>{tool.name}</span>
              <span style={{
                fontSize: 11, fontWeight: 500,
                color: tool.status === 'running' ? 'var(--red)' : tool.status === 'completed' ? 'var(--green)' : 'var(--text3)',
              }}>
                {tool.status === 'running' ? '运行中' : tool.status === 'completed' ? '完成' : '等待'}
              </span>
            </div>
            {tool.desc && <span style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 10, display: 'block' }}>{tool.desc}</span>}
            {/* Progress bar */}
            <div style={{ height: 3, background: 'var(--card)', borderRadius: 2, overflow: 'hidden', marginBottom: 10 }}>
              <div style={{
                height: '100%', borderRadius: 2, transition: 'width 0.3s ease',
                background: tool.status === 'completed' ? 'var(--green)' : 'linear-gradient(90deg, var(--red), var(--orange))',
                width: tool.status === 'completed' ? '100%' : '50%',
              }} />
            </div>
            {tool.result && (
              <div style={{
                fontSize: 12, color: 'var(--text2)', marginTop: 8, padding: '8px 10px',
                background: 'var(--card)', borderRadius: 6, lineHeight: 1.5,
                borderLeft: '2px solid var(--green)',
              }}>
                {typeof tool.result === 'string' ? tool.result : JSON.stringify(tool.result)}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  /* ── 证据面板 ── */
  const renderEvidencePanel = (evidence) => (
    <div className="phase-block" style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div style={{
          fontSize: 11, fontFamily: 'ui-monospace, monospace', fontWeight: 700,
          color: 'var(--red)', background: 'rgba(220, 38, 38, 0.1)',
          width: 28, height: 28, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>E</div>
        <span style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>证据池</span>
        <span style={{ fontSize: 12, color: 'var(--text3)' }}>{evidence.length} 条</span>
      </div>
      {evidence.map((ev, i) => (
        <div key={i} style={{ padding: '12px 0', borderBottom: i < evidence.length - 1 ? '1px solid var(--border)' : 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--red)' }}>
              {ev.type || ev.evidence_type || '数据'}
            </span>
            <span style={{ fontSize: 12, color: 'var(--text3)', fontFamily: 'ui-monospace, monospace' }}>
              {ev.source || ev.tool || ''}
            </span>
            {ev.confidence != null && (
              <span style={{
                fontSize: 12, fontWeight: 600,
                color: ev.confidence > 0.9 ? 'var(--green)' : ev.confidence > 0.8 ? 'var(--yellow)' : 'var(--text3)',
              }}>
                {(ev.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <p style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.5 }}>
            {ev.summary || ev.title || (typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data || ''))}
          </p>
          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text3)', marginTop: 4 }}>
            {ev.importance && <span>重要性: {ev.importance === 'high' ? '高' : '中'}</span>}
            {ev.date && <span>数据时间: {ev.date}</span>}
          </div>
        </div>
      ))}
    </div>
  );

  /* ── 校验面板 ── */
  const renderValidationPanel = (critic, compliance) => (
    <div className="phase-block" style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div style={{
          fontSize: 11, fontFamily: 'ui-monospace, monospace', fontWeight: 700,
          color: 'var(--red)', background: 'rgba(220, 38, 38, 0.1)',
          width: 28, height: 28, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>V</div>
        <span style={{ fontSize: 14, fontWeight: 600 }}>校验记录</span>
      </div>
      {critic && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Critic 校验</span>
            <span style={{ color: critic.passed ? 'var(--green)' : 'var(--red-bright)' }}>
              {critic.passed ? '通过' : '未通过'}
            </span>
            {critic.score != null && (
              <span style={{ fontSize: 13, fontFamily: 'ui-monospace, monospace', color: 'var(--text3)', marginLeft: 'auto' }}>
                评分 {critic.score}/100
              </span>
            )}
          </div>
          {critic.issues?.map((issue, i) => (
            <div key={i} style={{ fontSize: 13, color: 'var(--yellow)', marginTop: 6, paddingLeft: 8 }}>
              ⚠ {issue}
            </div>
          ))}
          {critic.missing_evidence?.length > 0 && (
            <div style={{ fontSize: 13, color: 'var(--text3)', marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
              缺失证据: {critic.missing_evidence.join(', ')}
            </div>
          )}
        </div>
      )}
      {compliance && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>合规校验</span>
            <span style={{ color: compliance.passed ? 'var(--green)' : 'var(--red-bright)' }}>
              {compliance.passed ? '通过' : '未通过'}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 13, color: 'var(--green)' }}>✓ 无确定性收益承诺</span>
            <span style={{ fontSize: 13, color: 'var(--green)' }}>✓ 无诱导交易表达</span>
            <span style={{ fontSize: 13, color: 'var(--green)' }}>✓ 已添加风险提示</span>
          </div>
        </div>
      )}
    </div>
  );

  /* ── 分析报告 ── */
  const renderReport = (answer) => {
    if (!answer) return null;
    const a = answer;
    return (
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 28, marginBottom: 20 }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 24, letterSpacing: '-0.01em' }}>分析结论</h3>

        {/* 总体结论 */}
        {a.summary && (
          <div style={{ marginBottom: 24 }}>
            <h4 className="report-section-title">总体结论</h4>
            <p style={{ fontSize: 15, color: 'var(--text)', lineHeight: 1.7 }}>{a.summary}</p>
          </div>
        )}

        {/* 关键判断 */}
        {a.key_points?.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h4 className="report-section-title">关键判断</h4>
            <ol style={{ paddingLeft: 20 }}>
              {a.key_points.map((p, i) => (
                <li key={i} style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.7, marginBottom: 8 }}>{p}</li>
              ))}
            </ol>
          </div>
        )}

        {/* 情景分析 */}
        {a.scenarios?.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h4 className="report-section-title">情景分析</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {a.scenarios.map((sc, i) => {
                const colors = ['var(--green)', 'var(--orange)', 'var(--red)'];
                return (
                  <div key={i} className="scenario-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{sc.name}</span>
                      <span style={{ fontSize: 14, fontFamily: 'ui-monospace, monospace', fontWeight: 700 }}>{sc.probability}%</span>
                    </div>
                    <div style={{ height: 4, background: 'var(--card)', borderRadius: 2, overflow: 'hidden', marginBottom: 10 }}>
                      <div style={{ height: '100%', borderRadius: 2, width: `${sc.probability}%`, background: colors[i] || colors[0], transition: 'width 0.6s ease' }} />
                    </div>
                    <p style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.5 }}>{sc.content}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 主要风险 */}
        {a.risks?.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h4 className="report-section-title">主要风险</h4>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {a.risks.map((r, i) => (
                <li key={i} style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.7, paddingLeft: 16, position: 'relative', marginBottom: 6 }}>
                  <span style={{ position: 'absolute', left: 0, top: 10, width: 6, height: 6, borderRadius: 3, background: 'var(--text3)' }} />
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 可选操作 */}
        {a.action_options?.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h4 className="report-section-title">可选操作</h4>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {a.action_options.map((op, i) => (
                <li key={i} style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.7, paddingLeft: 16, position: 'relative', marginBottom: 6 }}>
                  <span style={{ position: 'absolute', left: 0, top: 10, width: 6, height: 6, borderRadius: 3, background: 'var(--text3)' }} />
                  {op}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 数据限制 */}
        {a.data_limitations?.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h4 className="report-section-title">数据限制</h4>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {a.data_limitations.map((d, i) => (
                <li key={i} style={{ fontSize: 14, color: 'var(--yellow)', lineHeight: 1.7, paddingLeft: 16, position: 'relative', marginBottom: 6 }}>
                  <span style={{ position: 'absolute', left: 0, top: 10, width: 6, height: 6, borderRadius: 3, background: 'var(--text3)' }} />
                  {d}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 合规声明 */}
        <div className="compliance-banner">
          <span style={{ color: 'var(--yellow)', fontSize: 16, flexShrink: 0 }}>⚠</span>
          <span style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.6 }}>
            {a.compliance_disclaimer || '本分析基于公开数据和AI模型推演, 不构成投资建议。投资有风险, 决策需谨慎。'}
          </span>
        </div>
      </div>
    );
  };

  /* ── 渲染: 分析中 + 完成 ── */
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 24px 80px', width: '100%' }}>
      {/* 已完成的 turns */}
      {turns.map((turn, idx) => {
        if (expandedTurns[turn.id] === false) {
          // Collapsed
          const evCount = turn.evidenceItems?.length || 0;
          return (
            <div
              key={turn.id}
              onClick={() => setExpandedTurns(prev => ({ ...prev, [turn.id]: true }))}
              style={{
                background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12,
                padding: '16px 20px', marginBottom: 12, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 16,
              }}
            >
              <span style={{
                fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
                color: 'var(--red)', background: 'rgba(220, 38, 38, 0.1)', borderRadius: 4, padding: '2px 10px',
              }}>
                {turn.queryType === 'initial' ? '主问题' : `追问 ${idx}`}
              </span>
              <span style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>{turn.query}</span>
              <span style={{ fontSize: 12, color: 'var(--text3)', display: 'flex', gap: 12 }}>
                <span>{evCount} 条证据</span>
                <span>{turn.createdAt}</span>
              </span>
              <span style={{ fontSize: 12, color: 'var(--text3)' }}>展开 ▾</span>
            </div>
          );
        }
        return renderFlowCanvas(turn, idx, false);
      })}

      {/* Active analysis */}
      {phase === 'analyzing' && renderFlowCanvas({
        id: 'active', query: activeQuery,
        queryType: turns.length === 0 ? 'initial' : 'follow_up',
        createdAt: new Date().toLocaleString('zh-CN'),
      }, turns.length, true)}

      {/* Follow-up section */}
      {phase === 'done' && (
        <div style={{ marginTop: 24, paddingTop: 24, borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', marginBottom: 16 }}>
            <span style={{ color: 'var(--text3)', fontSize: 13 }}>当前上下文</span>
            <span style={{ color: 'var(--text2)', fontSize: 13 }}>
              {activeQuery} · {period} · {riskPref} · 累计 {turns.reduce((a, t) => a + (t.evidenceItems?.length || 0), 0)} 条证据
            </span>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleFollowUp(); } }}
              placeholder="继续追问这份研究..."
              style={{
                flex: 1, minHeight: 60, padding: '12px 16px',
                background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8,
                color: 'var(--text)', fontSize: 14, resize: 'vertical',
              }}
            />
            <button
              onClick={handleFollowUp}
              style={{
                padding: '12px 24px', borderRadius: 8, fontSize: 14, fontWeight: 600,
                background: 'linear-gradient(135deg, var(--red), var(--orange))', color: '#fff',
                whiteSpace: 'nowrap', height: 44,
              }}
            >
              继续分析
            </button>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
            {['如果周期改成半年呢？', '最大的风险是什么？', '和比亚迪相比呢？'].map((q, i) => (
              <button
                key={i}
                onClick={() => setQuery(q)}
                style={{
                  padding: '6px 14px', borderRadius: 6, fontSize: 13,
                  background: 'rgba(220, 38, 38, 0.08)', color: 'var(--text2)',
                  border: '1px solid rgba(220, 38, 38, 0.15)',
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ResearchChatView;
