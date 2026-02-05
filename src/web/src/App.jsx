import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, Cpu, Globe, Database, Settings, MessageSquare, 
  Loader2, Sparkles, Send, User, LogOut, FileText, ArrowRight,
  ChevronUp, ChevronDown, TrendingUp
} from 'lucide-react';
import { MOCK_CHART_DATA } from './services/mockService';
import AgentStatusNode from './components/ui/AgentStatusNode';
import ProgressBar from './components/ui/ProgressBar';
import QuickStarter from './components/ui/QuickStarter';
import StockChart from './components/dashboard/StockChart';
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
    const [isLogExpanded, setIsLogExpanded] = useState(true);
    const [showSettings, setShowSettings] = useState(false);
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [currentUser, setCurrentUser] = useState(null);
    const [citations, setCitations] = useState([]);
    const [chatSessionId, setChatSessionId] = useState('default');
    const [analysisResult, setAnalysisResult] = useState(null);
    const [riskPreference, setRiskPreference] = useState('稳健型 (蓝筹/红利)');
    const [investmentHorizon, setInvestmentHorizon] = useState('超短线 (打板/T+0)');
    const workflowTimerRef = useRef(null);
    const chatTimerRef = useRef(null);
  
    // Gemini State
    const [aiSummary, setAiSummary] = useState('');
    const [isAiGenerating, setIsAiGenerating] = useState(false);
    const [chatInput, setChatInput] = useState('');
    const [chatHistory, setChatHistory] = useState([]);
    const [isChatLoading, setIsChatLoading] = useState(false);

    const logsEndRef = useRef(null);
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

      if (workflowTimerRef.current) {
        clearInterval(workflowTimerRef.current);
        workflowTimerRef.current = null;
      }

      try {
        const trimmedQuery = query.trim();
        const isSymbol = /^(?:\d{6}|[A-Za-z]{2}\d{6}|\d{6}\.(?:SZ|SS))$/i.test(trimmedQuery);
          const preferences = {
            risk_preference: riskPreference,
            investment_horizon: investmentHorizon,
          };
          const response = isSymbol
            ? await startAnalyzeWorkflow(trimmedQuery, 20, preferences)
            : await startQueryWorkflow(trimmedQuery, preferences);

        setChatSessionId(response.session_id); // This line is retained as it is relevant to the current context.

        workflowTimerRef.current = setInterval(async () => {
          try {
            const status = await getWorkflowStatus(response.session_id);
            setProgress(status.progress || 0);
            setActiveLogs(
              (status.logs || []).map((log, idx) => ({
                agent: formatAgentLabel(log.agent),
                step: formatSafeStep(log, idx),
                text: formatSafeText(log),
                status: log.status,
                timestamp: log.timestamp,
              }))
            );

            if (status.status === 'completed') {
              clearInterval(workflowTimerRef.current);
              workflowTimerRef.current = null;
              setAppState('completed');
              setIsAiGenerating(false);
              const parsedResult = parseResult(status.result);
              setAnalysisResult(parsedResult);
              setAiSummary(buildSummary(parsedResult));
              loadCitations(parsedResult);
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

    useEffect(() => {
      if (logsEndRef.current) {
        logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [activeLogs]);

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
          investment_horizon: investmentHorizon,
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
                           <p className="font-medium text-white">{currentUser?.nickname || currentUser?.username || '用户'}</p>
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
                       <div className="grid grid-cols-2 gap-4">
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
                            <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">投资周期</label>
                            <select
                              className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-300"
                              value={investmentHorizon}
                              onChange={(e) => setInvestmentHorizon(e.target.value)}
                            >
                              <option>超短线 (打板/T+0)</option>
                              <option>波段操作 (周级别)</option>
                              <option>价值长持 (年级别)</option>
                            </select>
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
                <div className="max-w-4xl mx-auto mt-12 animate-in fade-in duration-500">
                  {/* Agent Workflow Map */}
                  <div className="flex justify-between items-center mb-8 px-8 md:px-16">
                     <AgentStatusNode icon={Database} label="数据获取" status={progress > 10 ? (progress > 30 ? 'done' : 'active') : 'pending'} />
                     <div className="h-0.5 flex-1 bg-slate-800 mx-2"></div>
                     <AgentStatusNode icon={Globe} label="数据分析" status={progress > 30 ? (progress > 60 ? 'done' : 'active') : 'pending'} />
                     <div className="h-0.5 flex-1 bg-slate-800 mx-2"></div>
                     <AgentStatusNode icon={Cpu} label="策略生成" status={progress > 60 ? (progress >= 100 ? 'done' : 'active') : 'pending'} />
                  </div>

                  {/* Thinking Chain (CoT) */}
                  <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 overflow-hidden shadow-2xl">
                    <div 
                      className="bg-white/5 px-4 py-2 flex items-center justify-between cursor-pointer"
                      onClick={() => setIsLogExpanded(!isLogExpanded)}
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                        <span className="text-sm font-medium text-slate-300">Agent Thinking Chain</span>
                      </div>
                      {isLogExpanded ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
                    </div>
                  
                    {isLogExpanded && (
                      <div className="p-4 h-56 overflow-y-auto font-mono text-xs md:text-sm space-y-2 bg-transparent">
                        {activeLogs.map((log, idx) => (
                          <div key={idx} className="flex gap-3 items-start animate-in fade-in slide-in-from-left-2">
                            <div className="text-blue-400 w-28 shrink-0 leading-5">[{log.agent}]</div>
                            <div className="min-w-0 flex-1">
                              {log.step && (
                                <div className="text-slate-500 text-[11px] mb-0.5">{log.step}</div>
                              )}
                              <div className="text-slate-300 break-words whitespace-pre-wrap">{log.text}</div>
                            </div>
                          </div>
                        ))}
                        <div ref={logsEndRef} />
                      </div>
                    )}
                  </div>
                
                  <ProgressBar progress={progress} />
                  <p className="text-center text-slate-500 text-sm mt-4 animate-pulse">正在编排多智能体网络...</p>
                </div>
              )}

              {/* --- Result Dashboard --- */}
              {appState === 'completed' && (
                <div className="mt-8 grid grid-cols-1 md:grid-cols-12 gap-6 animate-in fade-in slide-in-from-bottom-8 duration-700">
                
                  {/* 1. Executive Summary (Generated by Gemini) - Span 8 */}
                  <div className="md:col-span-12 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl relative overflow-hidden flex flex-col">
                     <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
                       投资建议 <Sparkles className="w-5 h-5 text-red-400 animate-pulse" />
                     </h2>
                   
                     {/* Gemini Content Area */}
                     <div className="flex-1">
                       {isAiGenerating ? (
                         <div className="space-y-3 animate-pulse">
                           <div className="h-4 bg-slate-700/50 rounded w-3/4"></div>
                           <div className="h-4 bg-slate-700/50 rounded w-full"></div>
                           <div className="h-4 bg-slate-700/50 rounded w-5/6"></div>
                           <div className="flex items-center gap-2 text-sm text-red-500 mt-4">
                             <Loader2 className="w-4 h-4 animate-spin" />
                             正在调用 Gemini 生成 A 股专业分析...
                           </div>
                         </div>
                       ) : (
                         <div
                           className="prose prose-invert prose-sm max-w-none text-slate-300 leading-relaxed"
                           dangerouslySetInnerHTML={{
                             __html: renderMarkdown(aiSummary || '分析完成。正在等待 AI 生成报告...'),
                           }}
                         />
                       )}
                     </div>

                     <div className="flex gap-4 mt-6 border-t border-white/10 pt-6 overflow-x-auto">
                       <div className="bg-slate-800/40 rounded-lg p-3 flex-1 border border-white/5 min-w-[100px]">
                         <p className="text-slate-500 text-xs uppercase font-bold mb-1">当前股价</p>
                         <p className="text-xl font-mono text-white">
                           {analysisResult?.stock_summary?.latest_close !== undefined
                             ? `¥${Number(analysisResult.stock_summary.latest_close).toFixed(2)}`
                             : '—'}
                         </p>
                       </div>
                       <div className="bg-slate-800/40 rounded-lg p-3 flex-1 border border-white/5 min-w-[100px]">
                         <p className="text-slate-500 text-xs uppercase font-bold mb-1">压力位</p>
                         <p className="text-xl font-mono text-white">
                           {analysisResult?.stock_summary?.high_max !== undefined
                             ? `¥${Number(analysisResult.stock_summary.high_max).toFixed(2)}`
                             : '—'}
                         </p>
                       </div>
                       <div className="bg-slate-800/40 rounded-lg p-3 flex-1 border border-white/5 min-w-[100px]">
                         <p className="text-slate-500 text-xs uppercase font-bold mb-1">止损位</p>
                         <p className="text-xl font-mono text-green-400">
                           {analysisResult?.stock_summary?.low_min !== undefined
                             ? `¥${Number(analysisResult.stock_summary.low_min).toFixed(2)}`
                             : '—'}
                         </p>
                       </div>
                       <div className="bg-slate-800/40 rounded-lg p-3 flex-1 border border-white/5 min-w-[100px]">
                         <p className="text-slate-500 text-xs uppercase font-bold mb-1">风险等级</p>
                         <p className="text-xl font-mono text-yellow-400">
                           {analysisResult?.stock_summary?.volatility_pct !== undefined
                             ? `${analysisResult.stock_summary.volatility_pct}%`
                             : '—'}
                         </p>
                       </div>
                     </div>
                  </div>

                  {/* 3. Interactive Chart - Full Span */}
                  <div className="md:col-span-12 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-4 shadow-xl">
                    <StockChart data={MOCK_CHART_DATA} />
                  </div>
                  {/* 4. Chat with Gemini (New Feature) - Span 5 */}
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
