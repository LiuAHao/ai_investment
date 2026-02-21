import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, Cpu, Globe, Database, Settings, MessageSquare, 
  Loader2, Sparkles, Send, User, LogOut, FileText, ArrowRight,
  TrendingUp
} from 'lucide-react';
import AgentStatusNode from './components/ui/AgentStatusNode';
import ProgressBar from './components/ui/ProgressBar';
import QuickStarter from './components/ui/QuickStarter';
import TypewriterText from './components/ui/TypewriterText';
import ProfileView from './components/views/ProfileView';
import SettingsView from './components/views/SettingsView';
import LandingView from './components/views/LandingView';
import AuthView from './components/views/AuthView';
import {
  getAuthToken,
  setAuthToken,
  fetchProfile,
  startAnalyzeWorkflow,
  startQueryWorkflow,
  getWorkflowStatus,
  sendChatMessage,
  fetchChatHistory,
  askChat,
} from './services/apiClient';

export default function InvestmentAgentApp() {
    const [query, setQuery] = useState('');
    const [appState, setAppState] = useState('idle');
    const [viewState, setViewState] = useState('landing');
    const [progress, setProgress] = useState(0);
    const [activeLogs, setActiveLogs] = useState([]);
    const [showSettings, setShowSettings] = useState(false);
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [currentUser, setCurrentUser] = useState(null);
    const [citations, setCitations] = useState([]);
    const [chatSessionId, setChatSessionId] = useState('default');
    const [analysisResult, setAnalysisResult] = useState(null);
    const [riskPreference, setRiskPreference] = useState('稳健型 (蓝筹/红利)');
    const [appMode, setAppMode] = useState('使用模式');
    const [agentOutputs, setAgentOutputs] = useState([]); // 存储各Agent的输出
    const [prevAgentCount, setPrevAgentCount] = useState(0); // 跟踪上一次Agent数量，用于打字机效果
    const workflowTimerRef = useRef(null);
    const chatTimerRef = useRef(null);
  
    // Gemini State
    const [aiSummary, setAiSummary] = useState('');
    const [isAiGenerating, setIsAiGenerating] = useState(false);
    const [chatInput, setChatInput] = useState('');
    const [chatHistory, setChatHistory] = useState([]);
    const [isChatLoading, setIsChatLoading] = useState(false);

    const chatEndRef = useRef(null);
    const userMenuRef = useRef(null);

    useEffect(() => {
      const initAuth = async () => {
        const token = getAuthToken();
        if (!token) return;
        try {
          const profile = await fetchProfile();
          setCurrentUser(profile);
          setViewState('main');
          await loadChatHistory(chatSessionId);
        } catch (error) {
          setAuthToken(null);
        }
      };

      initAuth();

      return () => {
        if (workflowTimerRef.current) clearInterval(workflowTimerRef.current);
        if (chatTimerRef.current) clearInterval(chatTimerRef.current);
      };
    }, []);

    const formatAgentLabel = (agent) => {
      const mapping = {
        DecisionAgent: '决策分析',
        NewsAgent: '新闻分析',
        StockAgent: '数据获取',
        MasterAgent: '任务编排',
        KnowledgeAgent: '知识检索',
      };
      return mapping[agent] || '执行中';
    };

    const getToolCategory = (stepText = '') => {
      const toolName = stepText.replace('工具结果-', '').trim();
      if (/query_investment_knowledge/i.test(toolName)) return '知识检索';
      if (/web_search|get_relevant_titles|news/i.test(toolName)) return '新闻检索';
      if (/stock_|get_stock/i.test(toolName)) return '行情处理';
      if (/sse|szse/i.test(toolName)) return '交易所数据';
      return '数据处理';
    };

    const formatSafeText = (log) => {
      const text = String(log?.text || '').trim();
      const step = String(log?.step || '');
      const hasToolKeyword = /工具|args=|query_investment_knowledge|web_search|get_stock|stock_|news_/i.test(text);
      if (hasToolKeyword || /工具结果/.test(step)) {
        return `已完成${getToolCategory(step)}`;
      }
      return text || '处理中...';
    };

    const formatSafeStep = (log, index) => {
      const step = String(log?.step || '').trim();
      if (!step) return '';
      if (/工具结果|工具/.test(step)) {
        const category = getToolCategory(step);
        return `数据处理 · ${category} #${index + 1}`;
      }
      return step;
    };

    const normalizeStageStatus = (status) => {
      if (status === 'completed' || status === 'done') return 'done';
      if (status === 'active' || status === 'processing') return 'active';
      if (status === 'failed') return 'failed';
      return 'pending';
    };

    const deriveStageProgress = () => {
      const stage = {
        planning: 'pending',
        execution: 'pending',
        summarize: 'pending',
      };

      for (const log of activeLogs) {
        const step = String(log?.step || '');
        const status = normalizeStageStatus(log?.status);

        if (/初始化|任务分解/.test(step)) {
          stage.planning = status === 'pending' ? stage.planning : status;
        }
        if (/阶段执行|数据/.test(step)) {
          if (status === 'failed') {
            stage.execution = 'failed';
          } else if (status === 'active' && stage.execution !== 'failed') {
            stage.execution = 'active';
          } else if (status === 'done' && stage.execution !== 'failed') {
            stage.execution = 'done';
          }
        }
        if (/结果生成|结果汇总/.test(step)) {
          stage.summarize = status === 'pending' ? stage.summarize : status;
        }
      }

      if (progress >= 20 && stage.planning === 'pending') stage.planning = 'done';
      if (progress >= 45 && stage.execution === 'pending') stage.execution = 'active';
      if (progress >= 80 && stage.execution === 'active') stage.execution = 'done';
      if (progress >= 90 && stage.summarize === 'pending') stage.summarize = 'active';
      if (progress >= 100) stage.summarize = 'done';

      return stage;
    };

    // 追踪agentOutputs变化，延迟更新prevAgentCount以触发打字机效果
    useEffect(() => {
      if (agentOutputs.length > prevAgentCount) {
        // 新Agent完成后，延迟2秒更新计数（给打字机动画留时间）
        const timer = setTimeout(() => {
          setPrevAgentCount(agentOutputs.length);
        }, 2000);
        return () => clearTimeout(timer);
      }
    }, [agentOutputs.length, prevAgentCount]);

    // Close user menu when clicking outside
    useEffect(() => {
      const handleClickOutside = (event) => {
        if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
          setShowUserMenu(false);
        }
      };

      if (showUserMenu) {
        document.addEventListener('mousedown', handleClickOutside);
      }
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }, [showUserMenu]);

    // Auto-scroll chat
    useEffect(() => {
      if (chatEndRef.current) {
        chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [chatHistory, isChatLoading]);

    // Simulate the AI Workflow
    const startAnalysis = async () => {
      if (!query) return;
      if (!getAuthToken()) {
        setViewState('login');
        return;
      }

      setAppState('processing');
      setProgress(0);
      setActiveLogs([]);
      setAiSummary('');
      setIsAiGenerating(true);
      setAgentOutputs([]); // 清空之前的Agent输出
      setPrevAgentCount(0); // 重置Agent计数

      if (workflowTimerRef.current) {
        clearInterval(workflowTimerRef.current);
        workflowTimerRef.current = null;
      }

      try {
        const trimmedQuery = query.trim();
        const isSymbol = /^(?:\d{6}|[A-Za-z]{2}\d{6}|\d{6}\.(?:SZ|SS))$/i.test(trimmedQuery);
          const preferences = {
            risk_preference: riskPreference,
            debug_mode: appMode === '调试模式',
            app_mode: appMode,
          };
          const response = isSymbol
            ? await startAnalyzeWorkflow(trimmedQuery, 20, preferences, query.trim())
            : await startQueryWorkflow(trimmedQuery, preferences);

        setChatSessionId(response.session_id); // This line is retained as it is relevant to the current context.

        workflowTimerRef.current = setInterval(async () => {
          try {
            const status = await getWorkflowStatus(response.session_id);
            setProgress(status.progress || 0);
            setActiveLogs(
              (status.logs || []).map((log, idx) => ({
                agent: formatAgentLabel(log.agent),
                rawAgent: log.agent,
                step: formatSafeStep(log, idx),
                text: formatSafeText(log),
                status: log.status,
                timestamp: log.timestamp,
              }))
            );

            // 实时提取中间Agent结果（在processing状态下也显示已完成的Agent）
            const parsedResult = parseResult(status.result);
            if (parsedResult?.agent_results && parsedResult.agent_results.length > 0) {
              setPrevAgentCount(prev => {
                // 只有新增的agent才触发打字机效果
                const newCount = parsedResult.agent_results.length;
                return prev < newCount ? prev : prev;
              });
              setAgentOutputs(parsedResult.agent_results);
            }

            if (status.status === 'completed') {
              clearInterval(workflowTimerRef.current);
              workflowTimerRef.current = null;
              setAppState('completed');
              setIsAiGenerating(false);
              setAnalysisResult(parsedResult);
              setAiSummary(buildSummary(parsedResult));
              loadCitations(parsedResult);
              // 最终结果中的agent_results
              if (parsedResult?.agent_results) {
                setAgentOutputs(parsedResult.agent_results);
              }
            }

            if (status.status === 'failed') {
              clearInterval(workflowTimerRef.current);
              workflowTimerRef.current = null;
              setIsAiGenerating(false);
              setAppState('completed');
              setAnalysisResult(null);
              setAiSummary(status.error || '分析失败');
            }
          } catch (error) {
            clearInterval(workflowTimerRef.current);
            workflowTimerRef.current = null;
            setIsAiGenerating(false);
            setAppState('completed');
            setAnalysisResult(null);
            setAiSummary(error.message || '获取分析状态失败');
          }
        }, 1000);
      } catch (error) {
        setIsAiGenerating(false);
        setAppState('completed');
        setAiSummary(error.message || '启动分析失败');
      }
    };

    // Feature 1: Generate Executive Summary via Gemini
    const loadCitations = (result) => {
      const webResults = result?.news_summary?.web_results || result?.web_results || [];
      if (!webResults.length) {
        setCitations([]);
        return;
      }
      const mapped = webResults.map((item, index) => {
        let source = item.source || '网络搜索';
        if (!item.source && item.link) {
          try {
            source = new URL(item.link).hostname;
          } catch (error) {
            source = '网络搜索';
          }
        }
        return {
          source,
          title: item.title || `结果 ${index + 1}`,
          url: item.link || '#',
          date: item.snippet ? '摘要' : `条目 ${index + 1}`,
        };
      });
      setCitations(mapped);
    };

    // Feature 2: Chat / Follow-up
    const handleChatSubmit = async (e) => {
      e?.preventDefault();
      if (!chatInput.trim()) return;
      if (!getAuthToken()) {
        setViewState('login');
        return;
      }

      const userMsg = { role: 'user', text: chatInput };
      setChatHistory(prev => [...prev, userMsg]);
      setChatInput('');
      setIsChatLoading(true);

      try {
        const preferences = {
          risk_preference: riskPreference,
          debug_mode: appMode === '调试模式',
          app_mode: appMode,
        };
        const response = await askChat(userMsg.text, chatSessionId, preferences);
        const aiText = response?.reply || '暂无结果';
        setChatHistory(prev => [...prev, { role: 'ai', text: aiText }]);
        setIsChatLoading(false);
      } catch (error) {
        setChatHistory(prev => [...prev, { role: 'ai', text: error.message || '查询失败' }]);
        setIsChatLoading(false);
      }
    };

    const loadChatHistory = async (sessionId) => {
      if (!getAuthToken()) return;
      try {
        const data = await fetchChatHistory(sessionId, 50, 0);
        const history = (data?.history || []).map((item) => ({
          role: item.role === 'assistant' ? 'ai' : item.role,
          text: item.content,
        }));
        setChatHistory(history);
      } catch (error) {
        setChatHistory([]);
      }
    };

    const parseResult = (result) => {
      if (!result) return null;
      if (typeof result === 'string') {
        const trimmed = result.trim();
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
          try {
            return JSON.parse(trimmed);
          } catch (error) {
            return result;
          }
        }
        return result;
      }
      return result;
    };

    const buildSummary = (result) => {
      if (!result) return '';
      if (typeof result === 'string') return result;
      // 通用查询的 response 字段
      if (result.response) return result.response;
      if (result.recommendation) return result.recommendation;
      const stock = result.stock_summary || {};
      const tech = result.tech_indicators || {};
      const news = result.news_summary || {};
      const lines = [];
      if (result.symbol) {
        lines.push(`标的：${result.symbol}`);
      }
      if (stock.latest_close !== undefined) {
        lines.push(`最新收盘价：¥${Number(stock.latest_close).toFixed(2)}`);
      }
      if (stock.total_return_pct !== undefined) {
        lines.push(`区间涨跌幅：${stock.total_return_pct}%`);
      }
      if (tech.trend) {
        lines.push(`趋势判断：${tech.trend}`);
      }
      if (news.total_titles !== undefined) {
        lines.push(`新闻覆盖：${news.total_titles} 条，相关 ${news.relevant_count || 0} 条`);
      }
      return lines.join('\n');
    };

    const escapeHtml = (value) => (
      value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
    );

    const renderMarkdown = (value) => {
      if (!value) return '';
      let html = escapeHtml(String(value));
      html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
      html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
      html = html.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\n{2,}/g, '</p><p>');
      html = html.replace(/\n/g, '<br />');
      html = `<p>${html}</p>`;
      return html;
    };

    const formatResult = (result) => {
      const parsed = parseResult(result);
      if (!parsed) return '';
      if (typeof parsed === 'string') return parsed;
      try {
        return JSON.stringify(parsed, null, 2);
      } catch (error) {
        return String(parsed);
      }
    };

    // 渲染单个Agent的输出卡片
    const renderAgentOutputCard = (agentResult, index, isNewAgent = false) => {
      const { agent, status, data, error, latency_ms } = agentResult;
      
      const agentConfig = {
        StockAgent: { 
          label: '数据Agent', 
          icon: Database, 
          color: 'blue',
          desc: '股票数据获取与技术分析'
        },
        NewsAgent: { 
          label: '新闻Agent', 
          icon: Globe, 
          color: 'green',
          desc: '新闻检索与情绪分析'
        },
        KnowledgeAgent: { 
          label: '知识Agent', 
          icon: Cpu, 
          color: 'purple',
          desc: '投资知识库检索'
        },
        AnalysisAgent: { 
          label: '分析Agent', 
          icon: Sparkles, 
          color: 'orange',
          desc: '综合分析与投资建议生成'
        },
      };
      
      const config = agentConfig[agent] || { label: agent, icon: Cpu, color: 'gray', desc: '' };
      const Icon = config.icon;
      
      const statusConfig = {
        completed: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', label: '已完成' },
        failed: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', label: '失败' },
        skipped: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400', label: '已跳过' },
        pending: { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', label: '等待中' },
      };
      const statusStyle = statusConfig[status] || statusConfig.completed;

      // 渲染StockAgent详细内容
      const renderStockDetail = (data) => {
        const summary = data?.summary || {};
        const technical = data?.technical || {};
        if (!summary.symbol && !summary.latest_close && !technical.trend) {
          return <p className="text-sm text-slate-400">当前查询不涉及具体股票分析，数据Agent未获取行情数据。</p>;
        }
        const changePct = summary.latest_change_pct;
        const changeColor = changePct >= 0 ? 'text-red-400' : 'text-green-400';
        const changeSign = changePct >= 0 ? '+' : '';
        const returnPct = summary.total_return_pct;
        const returnColor = returnPct >= 0 ? 'text-red-400' : 'text-green-400';
        const returnSign = returnPct >= 0 ? '+' : '';
        return (
          <div className="space-y-2.5">
            {/* 股票标题与区间 */}
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-blue-300">
                {summary.symbol || '未知'}
              </span>
              {summary.start_date && summary.end_date && (
                <span className="text-xs text-slate-500">
                  {summary.start_date} ~ {summary.end_date}
                </span>
              )}
            </div>
            {/* 价格核心指标 */}
            <div className="grid grid-cols-2 gap-2">
              {summary.latest_close !== undefined && (
                <div className="bg-slate-800/50 rounded-lg px-2.5 py-1.5">
                  <p className="text-xs text-slate-500">最新收盘</p>
                  <p className="text-sm font-medium text-white">
                    ¥{Number(summary.latest_close).toFixed(2)}
                    {changePct !== undefined && (
                      <span className={`ml-1 text-xs ${changeColor}`}>
                        {changeSign}{Number(changePct).toFixed(2)}%
                      </span>
                    )}
                  </p>
                </div>
              )}
              {returnPct !== undefined && (
                <div className="bg-slate-800/50 rounded-lg px-2.5 py-1.5">
                  <p className="text-xs text-slate-500">区间涨跌</p>
                  <p className={`text-sm font-medium ${returnColor}`}>
                    {returnSign}{Number(returnPct).toFixed(2)}%
                  </p>
                </div>
              )}
              {summary.high_max !== undefined && summary.low_min !== undefined && (
                <div className="bg-slate-800/50 rounded-lg px-2.5 py-1.5">
                  <p className="text-xs text-slate-500">价格区间</p>
                  <p className="text-sm text-slate-300">
                    ¥{Number(summary.low_min).toFixed(2)} ~ ¥{Number(summary.high_max).toFixed(2)}
                  </p>
                </div>
              )}
              {summary.volatility_pct !== undefined && (
                <div className="bg-slate-800/50 rounded-lg px-2.5 py-1.5">
                  <p className="text-xs text-slate-500">波动率</p>
                  <p className="text-sm text-slate-300">{Number(summary.volatility_pct).toFixed(2)}%</p>
                </div>
              )}
            </div>
            {/* 技术分析 */}
            {(technical.trend || technical.ma) && (
              <div className="bg-slate-800/40 rounded-lg px-2.5 py-2">
                <p className="text-xs text-slate-500 mb-1">技术分析</p>
                <div className="flex flex-wrap gap-1.5">
                  {technical.trend && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      technical.trend === '上行' ? 'bg-red-500/15 text-red-400' : 
                      technical.trend === '下行' ? 'bg-green-500/15 text-green-400' : 
                      'bg-yellow-500/15 text-yellow-400'
                    }`}>
                      趋势: {technical.trend}
                    </span>
                  )}
                  {technical.momentum_pct !== undefined && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      technical.momentum_pct >= 0 ? 'bg-red-500/15 text-red-400' : 'bg-green-500/15 text-green-400'
                    }`}>
                      动量: {technical.momentum_pct >= 0 ? '+' : ''}{Number(technical.momentum_pct).toFixed(2)}%
                    </span>
                  )}
                </div>
                {technical.ma && Object.keys(technical.ma).length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-400">
                    {Object.entries(technical.ma).map(([key, val]) => (
                      <span key={key}>{key.toUpperCase()}: ¥{Number(val).toFixed(2)}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
            {/* 成交量信息 */}
            {(summary.avg_volume || summary.avg_amount) && (
              <div className="flex gap-3 text-xs text-slate-500">
                {summary.avg_volume && (
                  <span>日均成交量: {Number(summary.avg_volume) >= 10000 ? 
                    (Number(summary.avg_volume) / 10000).toFixed(1) + '万' : 
                    Number(summary.avg_volume).toFixed(0)}手</span>
                )}
                {summary.avg_amount && (
                  <span>日均成交额: {Number(summary.avg_amount) >= 100000000 ? 
                    (Number(summary.avg_amount) / 100000000).toFixed(2) + '亿' : 
                    (Number(summary.avg_amount) / 10000).toFixed(0) + '万'}</span>
                )}
              </div>
            )}
          </div>
        );
      };

      // 渲染NewsAgent详细内容
      const renderNewsDetail = (data) => {
        const webResults = data?.web_results || [];
        const relevantTitles = data?.relevant_titles || [];
        const totalCount = data?.total_titles || relevantTitles.length;
        
        return (
          <div className="space-y-2.5">
            {/* 概要统计 */}
            <div className="flex items-center gap-3 text-xs">
              {totalCount > 0 && (
                <span className="text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">
                  {totalCount} 条新闻
                </span>
              )}
              {webResults.length > 0 && (
                <span className="text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full">
                  {webResults.length} 条网络搜索
                </span>
              )}
              {totalCount === 0 && webResults.length === 0 && (
                <span className="text-yellow-400 bg-yellow-500/10 px-2 py-0.5 rounded-full">
                  未检索到相关新闻
                </span>
              )}
            </div>
            {/* 新闻列表 */}
            {webResults.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-slate-500">市场资讯：</p>
                {webResults.slice(0, 4).map((item, i) => (
                  <div key={i} className="bg-slate-800/40 rounded-lg px-2.5 py-1.5">
                    <p className="text-xs text-slate-200 font-medium leading-snug">
                      {item.title || '无标题'}
                    </p>
                    {item.snippet && (
                      <p className="text-xs text-slate-500 mt-0.5 line-clamp-2 leading-relaxed">
                        {item.snippet.length > 80 ? item.snippet.slice(0, 80) + '…' : item.snippet}
                      </p>
                    )}
                  </div>
                ))}
                {webResults.length > 4 && (
                  <p className="text-xs text-slate-500 text-center">
                    还有 {webResults.length - 4} 条更多资讯…
                  </p>
                )}
              </div>
            )}
            {/* 相关标题 */}
            {relevantTitles.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs text-slate-500">相关标题：</p>
                {relevantTitles.slice(0, 3).map((title, i) => (
                  <p key={i} className="text-xs text-slate-300 pl-2 border-l border-green-500/30">
                    {title}
                  </p>
                ))}
              </div>
            )}
            {totalCount === 0 && webResults.length === 0 && (
              <p className="text-xs text-slate-500">建议关注后续市场动态以获取更多信息。</p>
            )}
          </div>
        );
      };

      // 渲染KnowledgeAgent详细内容
      const renderKnowledgeDetail = (data) => {
        const results = data?.results || [];
        const citations = data?.citations || [];
        const fallback = data?.fallback;
        const message = data?.message;
        
        if (results.length === 0) {
          return (
            <div className="space-y-2">
              <p className="text-sm text-slate-400">
                未找到直接匹配的知识片段。系统将基于通用分析框架继续评估。
              </p>
              {message && (
                <p className="text-xs text-yellow-400/70">提示: {message}</p>
              )}
            </div>
          );
        }
        
        // 提取涉及的主题领域
        const topics = [];
        results.slice(0, 5).forEach(item => {
          const content = item.text || item.content || '';
          if (content.includes('估值')) topics.push('估值方法');
          if (content.includes('技术')) topics.push('技术分析');
          if (content.includes('财务')) topics.push('财务指标');
          if (content.includes('风险')) topics.push('风险控制');
          if (content.includes('行业')) topics.push('行业研究');
          if (content.includes('宏观')) topics.push('宏观分析');
          if (content.includes('策略')) topics.push('投资策略');
          if (content.includes('交易')) topics.push('交易规则');
        });
        const uniqueTopics = [...new Set(topics)];
        
        return (
          <div className="space-y-2.5">
            {/* 概要 */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full">
                {results.length} 条知识匹配
              </span>
              {fallback && (
                <span className="text-xs text-yellow-400 bg-yellow-500/10 px-2 py-0.5 rounded-full">
                  覆盖不足
                </span>
              )}
            </div>
            {/* 涉及领域标签 */}
            {uniqueTopics.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {uniqueTopics.map((topic, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300">
                    {topic}
                  </span>
                ))}
              </div>
            )}
            {/* 知识片段摘要 */}
            <div className="space-y-1.5">
              {results.slice(0, 3).map((item, i) => {
                const text = item.text || item.content || '';
                const excerpt = text.length > 100 ? text.slice(0, 100) + '…' : text;
                const meta = item.metadata || {};
                const title = meta.title || citations[i]?.title || '';
                return (
                  <div key={i} className="bg-slate-800/40 rounded-lg px-2.5 py-1.5">
                    {title && (
                      <p className="text-xs text-purple-300 font-medium">{title}</p>
                    )}
                    <p className="text-xs text-slate-400 leading-relaxed mt-0.5">{excerpt}</p>
                  </div>
                );
              })}
              {results.length > 3 && (
                <p className="text-xs text-slate-500 text-center">
                  还有 {results.length - 3} 条相关知识…
                </p>
              )}
            </div>
          </div>
        );
      };

      // 渲染AnalysisAgent详细内容
      const renderAnalysisDetail = (data) => {
        const recommendation = data?.recommendation;
        if (!recommendation) {
          return <p className="text-sm text-slate-400">正在生成分析结论…</p>;
        }
        const recText = typeof recommendation === 'string' ? recommendation : JSON.stringify(recommendation);
        
        // 提取关键信号
        const signals = [];
        if (recText.includes('观望') || recText.includes('谨慎')) signals.push({ label: '观望', color: 'yellow' });
        if (recText.includes('买入') || recText.includes('增持')) signals.push({ label: '偏多', color: 'red' });
        if (recText.includes('卖出') || recText.includes('减持')) signals.push({ label: '偏空', color: 'green' });
        if (recText.includes('风险')) signals.push({ label: '关注风险', color: 'orange' });
        if (recText.includes('机会') || recText.includes('利好')) signals.push({ label: '存在机会', color: 'blue' });
        
        // 截取前200字作为摘要
        const excerpt = recText.length > 200 ? recText.slice(0, 200) + '…' : recText;
        
        return (
          <div className="space-y-2.5">
            {/* 信号标签 */}
            {signals.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {signals.map((s, i) => (
                  <span key={i} className={`text-xs px-2 py-0.5 rounded-full bg-${s.color}-500/15 text-${s.color}-400`}>
                    {s.label}
                  </span>
                ))}
              </div>
            )}
            {/* 分析摘要 */}
            <div className="bg-slate-800/40 rounded-lg px-2.5 py-2">
              <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                {excerpt}
              </p>
            </div>
            {recText.length > 200 && (
              <p className="text-xs text-slate-500">完整分析请查看下方投资建议报告。</p>
            )}
          </div>
        );
      };

      // 根据Agent类型选择渲染函数
      const renderAgentDetail = () => {
        if (!data || Object.keys(data).length === 0) {
          return <p className="text-sm text-slate-400">该Agent未返回有效数据。</p>;
        }
        if (data.reason) {
          return <p className="text-sm text-yellow-400">{data.reason}</p>;
        }
        switch (agent) {
          case 'StockAgent': return renderStockDetail(data);
          case 'NewsAgent': return renderNewsDetail(data);
          case 'KnowledgeAgent': return renderKnowledgeDetail(data);
          case 'AnalysisAgent': return renderAnalysisDetail(data);
          default: return <p className="text-sm text-slate-300">该Agent已完成任务。</p>;
        }
      };
      
      return (
        <div key={index} className={`rounded-xl border ${statusStyle.border} ${statusStyle.bg} p-4 transition-all hover:scale-[1.02]`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-lg bg-${config.color}-500/20 flex items-center justify-center`}>
                <Icon className={`w-4 h-4 text-${config.color}-400`} />
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-200">{config.label}</h4>
                <p className="text-xs text-slate-500">{config.desc}</p>
              </div>
            </div>
            <div className="text-right">
              <span className={`text-xs px-2 py-1 rounded-full ${statusStyle.bg} ${statusStyle.text}`}>
                {statusStyle.label}
              </span>
              {latency_ms > 0 && (
                <p className="text-xs text-slate-500 mt-1">{latency_ms}ms</p>
              )}
            </div>
          </div>
          
          <div className="mt-3">
            {status === 'failed' && error ? (
              <div className="text-xs text-red-400 bg-red-500/10 rounded px-2 py-1.5">
                <TypewriterText text={`错误: ${error}`} speed={15} className="text-red-400" />
              </div>
            ) : status === 'skipped' ? (
              <div className="text-xs text-yellow-400 bg-yellow-500/10 rounded px-2 py-1.5">
                <TypewriterText text={data?.reason || '该阶段已跳过'} speed={15} className="text-yellow-400" />
              </div>
            ) : (
              renderAgentDetail()
            )}
          </div>
        </div>
      );
    };

    const handleQuickStart = (text) => {
      setQuery(text);
    };

    const handleLogout = () => {
      setShowUserMenu(false);
      setViewState('landing');
      setAppState('idle');
      setQuery('');
      setCurrentUser(null);
      setAuthToken(null);
      setChatHistory([]);
      setCitations([]);
      setAnalysisResult(null);
    };

    const handleViewChange = (view) => {
      setViewState(view);
      setShowUserMenu(false);
    };

    // Helper to determine if we are in the main app layout (with header)
    const isMainAppLayout = ['main', 'profile', 'settings'].includes(viewState);

    return (
      <div className="min-h-screen text-slate-200 font-sans selection:bg-red-500/30 relative overflow-x-hidden">
      
        {/* --- Premium Background Layer (Global) --- */}
        <div className="fixed inset-0 -z-10 h-full w-full bg-slate-950">
          {/* Subtle Grid Pattern */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
          {/* Top Center Red Glow */}
          <div className="absolute left-0 right-0 top-[-10%] h-[500px] w-full rounded-full bg-[radial-gradient(circle_farthest-side,rgba(220,38,38,0.12),rgba(255,255,255,0))] blur-3xl"></div>
          {/* Bottom Right Warm Glow */}
          <div className="absolute bottom-0 right-[-10%] h-[500px] w-[500px] rounded-full bg-[radial-gradient(circle_farthest-side,rgba(234,88,12,0.08),rgba(255,255,255,0))] blur-[100px]"></div>
        </div>

        {/* --- View Routing --- */}

        {/* Landing Page */}
        {viewState === 'landing' && <LandingView setViewState={setViewState} />}

        {/* Auth Pages */}
        {(viewState === 'login' || viewState === 'register') && (
          <AuthView
            viewState={viewState}
            setViewState={setViewState}
            onAuthSuccess={async (token) => {
              setAuthToken(token);
              try {
                const profile = await fetchProfile();
                setCurrentUser(profile);
                setViewState('main');
                await loadChatHistory(chatSessionId);
              } catch (error) {
                setAuthToken(null);
              }
            }}
          />
        )}

        {/* Main App Layout */}
        {isMainAppLayout && (
          <>
            {/* Header */}
            <header className="fixed top-0 w-full z-50 bg-slate-950/50 backdrop-blur-md border-b border-white/10">
              <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
                <div className="flex items-center gap-2 cursor-pointer" onClick={() => setViewState('main')}>
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-orange-600 flex items-center justify-center shadow-lg shadow-red-500/20">
                    <TrendingUp className="text-white w-5 h-5" />
                  </div>
                  <span className="font-bold text-lg tracking-tight text-white">AI投资助手</span>
                </div>
                <div className="flex items-center gap-4">
                   {/* User Avatar with Menu */}
                   <div className="relative" ref={userMenuRef}>
                     <button 
                       onClick={() => setShowUserMenu(!showUserMenu)}
                       className="w-9 h-9 rounded-full bg-gradient-to-br from-red-500 to-orange-600 border-2 border-slate-700 hover:border-red-500 transition-all flex items-center justify-center text-white text-[10px] font-bold shadow-lg px-1 text-center leading-tight"
                     >
                       {currentUser?.nickname || currentUser?.username || 'AI'}
                     </button>
                   
                     {/* User Dropdown Menu */}
                     {showUserMenu && (
                       <div className="absolute right-0 top-full mt-2 w-56 bg-slate-900/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 z-50">
                         {/* User Info */}
                         <div className="px-4 py-3 border-b border-white/10">
                           <div className="flex items-center gap-2">
                             <p className="font-medium text-white">{currentUser?.nickname || currentUser?.username || '用户'}</p>
                             <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                               currentUser?.user_tier === 'premium' ? 'bg-amber-500/20 text-amber-300' :
                               currentUser?.user_tier === 'pro' ? 'bg-blue-500/20 text-blue-300' :
                               'bg-slate-500/20 text-slate-400'
                             }`}>
                               {currentUser?.user_tier === 'premium' ? '旗舰版' : currentUser?.user_tier === 'pro' ? '专业版' : '免费版'}
                             </span>
                           </div>
                           <p className="text-xs text-slate-400">{currentUser?.email || '未设置邮箱'}</p>
                         </div>
                       
                         {/* Menu Items */}
                         <div className="py-2">
                           <button
                             onClick={() => handleViewChange('profile')}
                             className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-white/5 transition-colors text-left"
                           >
                             <User className="w-4 h-4 text-slate-400" />
                             <span className="text-sm text-slate-300">个人账户</span>
                           </button>
                           <button
                             onClick={() => handleViewChange('settings')}
                             className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-white/5 transition-colors text-left"
                           >
                             <Settings className="w-4 h-4 text-slate-400" />
                             <span className="text-sm text-slate-300">设置</span>
                           </button>
                           {currentUser?.user_tier !== 'premium' && (
                             <button
                               onClick={() => handleViewChange('profile')}
                               className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-amber-500/10 transition-colors text-left"
                             >
                               <Sparkles className="w-4 h-4 text-amber-400" />
                               <span className="text-sm text-amber-300">升级会员</span>
                             </button>
                           )}
                         </div>
                       
                         {/* Logout */}
                         <div className="border-t border-white/10 py-2">
                           <button
                             onClick={handleLogout}
                             className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-red-500/10 transition-colors text-left"
                           >
                             <LogOut className="w-4 h-4 text-red-400" />
                             <span className="text-sm text-red-400">退出登录</span>
                           </button>
                         </div>
                       </div>
                     )}
                   </div>
                </div>
              </div>
            </header>

            <main className="pt-24 pb-12 px-4 max-w-7xl mx-auto">
            
              {/* Render different views based on viewState */}
              {viewState === 'profile' && (
                <ProfileView
                  setViewState={setViewState}
                  user={currentUser}
                  onProfileUpdated={setCurrentUser}
                />
              )}
              {viewState === 'settings' && <SettingsView setViewState={setViewState} />}
            
              {/* Main Investment Analysis View */}
              {viewState === 'main' && (
                <div>
              {/* --- Interaction Section (Omnibox) --- */}
              <section className={`transition-all duration-700 ease-in-out ${appState === 'idle' ? 'translate-y-[20vh]' : 'translate-y-0'} relative z-30`}>
                <div className="max-w-3xl mx-auto text-center mb-8">
                  {appState === 'idle' && (
                    <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 tracking-tight drop-shadow-xl">
                      AI 驱动的<span className="text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-orange-500">A股深度投研</span>
                    </h1>
                  )}
                </div>

                <div className="max-w-2xl mx-auto relative group z-20">
                  <div className={`absolute -inset-0.5 bg-gradient-to-r from-red-500 to-orange-600 rounded-xl opacity-30 group-hover:opacity-60 blur transition duration-1000 group-hover:duration-200 ${appState !== 'idle' ? 'opacity-0' : ''}`}></div>
                  <div className="relative flex items-center bg-slate-900/80 backdrop-blur-xl rounded-xl border border-white/10 shadow-2xl overflow-hidden z-10">
                    <div className="pl-4 text-slate-500">
                      <Search className="w-5 h-5" />
                    </div>
                    <input 
                      type="text" 
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && startAnalysis()}
                      placeholder="输入股票代码 (如 300750) 或自然语言提问..."
                      className="w-full bg-transparent border-none px-4 py-4 text-lg text-white placeholder-slate-500 focus:outline-none focus:ring-0"
                    />
                    <div className="pr-2 flex items-center gap-2">
                       <button 
                        onClick={() => setShowSettings(!showSettings)}
                        className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors"
                      >
                         <Settings className="w-4 h-4" />
                       </button>
                       <button 
                        onClick={startAnalysis}
                        className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
                       >
                         分析
                       </button>
                    </div>
                  </div>

                  {/* Config Panel Popover */}
                  {showSettings && (
                     <div className="absolute top-full mt-2 left-0 right-0 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl p-4 shadow-xl z-50 animate-in fade-in slide-in-from-top-2">
                       <div className="grid grid-cols-1 gap-4">
                          <div>
                            <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">风险偏好</label>
                            <select
                              className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-300"
                              value={riskPreference}
                              onChange={(e) => setRiskPreference(e.target.value)}
                            >
                              <option>稳健型 (蓝筹/红利)</option>
                              <option>激进型 (题材/成长)</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">运行模式</label>
                            <select
                              className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-300"
                              value={appMode}
                              onChange={(e) => setAppMode(e.target.value)}
                            >
                              <option>使用模式</option>
                              <option>调试模式</option>
                            </select>
                            <p className="text-[11px] text-slate-500 mt-2">
                              使用模式隐藏内部异常细节；调试模式会展示链路与缺失原因。
                            </p>
                          </div>
                       </div>
                     </div>
                  )}
                </div>

                {/* Quick Starters */}
                {appState === 'idle' && (
                  <div className="max-w-2xl mx-auto mt-6 flex flex-wrap gap-2 justify-center animate-in fade-in slide-in-from-bottom-4 duration-700">
                    <QuickStarter text="宁德时代财报分析" onClick={() => handleQuickStart("宁德时代财报分析")} />
                    <QuickStarter text="今日 A 股复盘" onClick={() => handleQuickStart("今日 A 股复盘")} />
                    <QuickStarter text="半导体资金流向" onClick={() => handleQuickStart("半导体资金流向")} />
                    <QuickStarter text="央行降准影响" onClick={() => handleQuickStart("央行降准影响")} />
                  </div>
                )}
              </section>

              {/* --- Process Visualization (The "Wait" State) --- */}
              {appState === 'processing' && (
                <div className="max-w-5xl mx-auto mt-12 animate-in fade-in duration-500">
                  {(() => {
                    const stage = deriveStageProgress();

                    return (
                      <>
                  {/* Agent Workflow Map */}
                  <div className="flex justify-between items-center mb-8 px-8 md:px-16">
                     <AgentStatusNode
                       icon={Database}
                       label="任务分解"
                       status={stage.planning === 'done' ? 'done' : stage.planning === 'active' ? 'active' : 'pending'}
                     />
                     <div className="h-0.5 flex-1 bg-slate-800 mx-2"></div>
                     <AgentStatusNode
                       icon={Globe}
                       label="数据执行"
                       status={stage.execution === 'done' ? 'done' : stage.execution === 'active' ? 'active' : 'pending'}
                     />
                     <div className="h-0.5 flex-1 bg-slate-800 mx-2"></div>
                     <AgentStatusNode
                       icon={Cpu}
                       label="结果生成"
                       status={stage.summarize === 'done' ? 'done' : stage.summarize === 'active' ? 'active' : 'pending'}
                     />
                  </div>

                  <ProgressBar progress={progress} />
                  
                  {/* 渐进式实时显示已完成的Agent输出卡片 */}
                  <div className="mt-8">
                    <h3 className="text-sm font-medium text-slate-400 mb-4 flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-blue-400" />
                      Agent 执行进度
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* 已完成的Agent - 显示所有结果（不过滤） */}
                      {agentOutputs.map((agentResult, index) => (
                        <div 
                          key={`agent-${agentResult.agent}`} 
                          className="animate-in fade-in slide-in-from-left-4 duration-500"
                          style={{ animationDelay: `${index * 150}ms` }}
                        >
                          {renderAgentOutputCard(agentResult, index, index >= prevAgentCount)}
                        </div>
                      ))}
                      {/* 未完成的Agent - 显示 pending 占位卡片 */}
                      {(() => {
                        const expectedAgents = ['StockAgent', 'NewsAgent', 'KnowledgeAgent', 'AnalysisAgent'];
                        const completedAgentNames = agentOutputs.map(a => a.agent);
                        const pendingAgents = expectedAgents.filter(a => !completedAgentNames.includes(a));
                        return pendingAgents.map((agentName, idx) => (
                          <div 
                            key={`pending-${agentName}`}
                            className="rounded-xl border border-slate-500/20 bg-slate-500/5 p-4 transition-all"
                          >
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-2">
                                <div className="w-8 h-8 rounded-lg bg-slate-500/20 flex items-center justify-center">
                                  <Loader2 className="w-4 h-4 text-slate-500 animate-spin" />
                                </div>
                                <div>
                                  <h4 className="text-sm font-medium text-slate-400">
                                    {({StockAgent: '数据Agent', NewsAgent: '新闻Agent', KnowledgeAgent: '知识Agent', AnalysisAgent: '分析Agent'})[agentName]}
                                  </h4>
                                  <p className="text-xs text-slate-600">等待执行</p>
                                </div>
                              </div>
                              <span className="text-xs px-2 py-1 rounded-full bg-slate-500/10 text-slate-500">
                                等待中
                              </span>
                            </div>
                            <div className="mt-3">
                              <div className="space-y-2 animate-pulse">
                                <div className="h-3 bg-slate-700/30 rounded w-3/4"></div>
                                <div className="h-3 bg-slate-700/30 rounded w-1/2"></div>
                              </div>
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>
                  
                  {/* 实时Agent执行日志 */}
                  {activeLogs.length > 0 && (
                    <div className="mt-8 bg-slate-900/40 backdrop-blur-sm rounded-xl border border-white/5 p-4">
                      <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Agent 执行日志
                      </h3>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {activeLogs.slice(-6).map((log, index) => (
                          <div 
                            key={index} 
                            className={`flex items-center gap-3 text-sm p-2 rounded-lg transition-all ${
                              log.status === 'active' ? 'bg-blue-500/10 border border-blue-500/20' : 'bg-slate-800/30'
                            }`}
                          >
                            <span className={`w-2 h-2 rounded-full ${
                              log.status === 'completed' ? 'bg-green-400' :
                              log.status === 'failed' ? 'bg-red-400' :
                              log.status === 'active' ? 'bg-blue-400 animate-pulse' :
                              'bg-slate-500'
                            }`}></span>
                            <span className="text-slate-400 w-20 shrink-0">{log.agent}</span>
                            <span className="text-slate-300 flex-1">{log.text}</span>
                            {log.status === 'active' && (
                              <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <p className="text-center text-slate-500 text-sm mt-4 animate-pulse">正在编排多智能体网络...</p>
                      </>
                    );
                  })()}
                </div>
              )}

              {/* --- Result Dashboard --- */}
              {appState === 'completed' && (
                <div className="mt-8 grid grid-cols-1 md:grid-cols-12 gap-6 animate-in fade-in slide-in-from-bottom-8 duration-700">
                
                  {/* 1. Agent 执行过程展示 */}
                  {agentOutputs.length > 0 && (
                    <div className="md:col-span-12">
                      <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                        <Cpu className="w-5 h-5 text-blue-400" />
                        Agent 分析过程
                      </h2>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {agentOutputs.map((agentResult, index) => renderAgentOutputCard(agentResult, index, false))}
                      </div>
                    </div>
                  )}
                  
                  {/* 分隔线 */}
                  {agentOutputs.length > 0 && (
                    <div className="md:col-span-12">
                      <div className="h-px bg-gradient-to-r from-transparent via-slate-600 to-transparent my-2"></div>
                    </div>
                  )}
                
                  {/* 2. 最终投资建议 */}
                  <div className="md:col-span-12 bg-gradient-to-br from-slate-900/80 to-slate-800/60 backdrop-blur-md rounded-2xl border border-red-500/20 p-6 shadow-xl relative overflow-hidden flex flex-col">
                     {/* 装饰背景 */}
                     <div className="absolute top-0 right-0 w-64 h-64 bg-red-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
                     
                     <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2 relative z-10">
                       <Sparkles className="w-6 h-6 text-red-400" />
                       最终投资建议
                     </h2>
                   
                     {/* 投资建议内容区域 */}
                     <div className="flex-1 relative z-10">
                       {isAiGenerating ? (
                         <div className="space-y-3 animate-pulse">
                           <div className="h-4 bg-slate-700/50 rounded w-3/4"></div>
                           <div className="h-4 bg-slate-700/50 rounded w-full"></div>
                           <div className="h-4 bg-slate-700/50 rounded w-5/6"></div>
                           <div className="flex items-center gap-2 text-sm text-red-500 mt-4">
                             <Loader2 className="w-4 h-4 animate-spin" />
                             正在生成投资建议...
                           </div>
                         </div>
                       ) : (
                         <div className="space-y-4">
                           {/* 简要摘要 */}
                           {aiSummary && (
                             <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                               <h3 className="text-sm font-medium text-slate-400 mb-2">分析摘要</h3>
                               <div
                                 className="prose prose-invert prose-sm max-w-none text-slate-300 leading-relaxed"
                                 dangerouslySetInnerHTML={{
                                   __html: renderMarkdown(aiSummary),
                                 }}
                               />
                             </div>
                           )}
                           
                           {/* 完整投资建议 */}
                           {analysisResult?.recommendation && (
                             <div className="bg-gradient-to-r from-red-500/10 to-orange-500/10 rounded-xl p-4 border border-red-500/20">
                               <h3 className="text-sm font-medium text-red-400 mb-2 flex items-center gap-2">
                                 <TrendingUp className="w-4 h-4" />
                                 综合建议
                               </h3>
                               <div
                                 className="prose prose-invert prose-sm max-w-none text-slate-200 leading-relaxed"
                                 dangerouslySetInnerHTML={{
                                   __html: renderMarkdown(analysisResult.recommendation),
                                 }}
                               />
                             </div>
                           )}
                           
                           {/* 无结果提示 */}
                           {!aiSummary && !analysisResult?.recommendation && (
                             <div className="text-slate-400 text-center py-8">
                               分析完成，暂无详细建议生成
                             </div>
                           )}
                         </div>
                       )}
                     </div>

                  </div>

                  {/* 3. Chat with Gemini (New Feature) - Span 5 */}
                  <div className="md:col-span-12 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-xl overflow-hidden flex flex-col h-[320px]">
                     <div className="p-4 border-b border-white/10 bg-white/5 flex justify-between items-center">
                       <h3 className="text-white font-bold flex items-center gap-2">
                         <MessageSquare className="w-4 h-4 text-red-400" />
                         AI 深度问答
                       </h3>
                     </div>
                   
                     {/* Chat History */}
                     <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-transparent">
                       {chatHistory.length === 0 ? (
                         <div className="text-center text-slate-500 text-sm mt-8">
                           <Sparkles className="w-8 h-8 mx-auto mb-2 text-slate-700" />
                           <p>对当前的分析有疑问？</p>
                           <p>试试问: "主力资金流向如何？"</p>
                         </div>
                       ) : (
                         chatHistory.map((msg, i) => (
                           <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                             <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                               msg.role === 'user' 
                                 ? 'bg-red-600 text-white rounded-br-none' 
                                 : 'bg-slate-800 text-slate-200 rounded-bl-none border border-slate-700'
                             }`}>
                               {msg.text}
                             </div>
                           </div>
                         ))
                       )}
                       {isChatLoading && (
                         <div className="flex justify-start">
                           <div className="bg-slate-800 rounded-2xl rounded-bl-none px-4 py-3 border border-slate-700 flex gap-1">
                             <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce"></span>
                             <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce delay-75" style={{ animationDelay: '0.1s' }}></span>
                             <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce delay-150" style={{ animationDelay: '0.2s' }}></span>
                           </div>
                         </div>
                       )}
                       <div ref={chatEndRef} />
                     </div>

                     {/* Chat Input */}
                     <form onSubmit={handleChatSubmit} className="p-3 bg-white/5 border-t border-white/10">
                       <div className="relative">
                         <input
                           type="text"
                           value={chatInput}
                           onChange={(e) => setChatInput(e.target.value)}
                           placeholder="输入问题..."
                           className="w-full bg-slate-800/50 border border-slate-700 text-slate-200 text-sm rounded-lg pl-4 pr-10 py-2.5 focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/50 transition-colors"
                         />
                         <button 
                           type="submit"
                           disabled={isChatLoading || !chatInput.trim()}
                           className="absolute right-1.5 top-1.5 p-1.5 bg-red-600 hover:bg-red-500 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                         >
                           <Send className="w-3 h-3" />
                         </button>
                       </div>
                     </form>
                  </div>

                </div>
              )}
            </div>
            )}
          </main>
        </>
      )}
    </div>
  );
}
