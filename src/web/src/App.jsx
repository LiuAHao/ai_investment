import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, Cpu, Globe, Database, Settings, MessageSquare, 
  Loader2, Sparkles, Send, User, LogOut, FileText, ArrowRight,
  ChevronUp, ChevronDown, TrendingUp
} from 'lucide-react';
import { MOCK_LOGS, CITATIONS, MOCK_CHART_DATA, getMockResponse } from './services/mockService';
import AgentStatusNode from './components/ui/AgentStatusNode';
import ProgressBar from './components/ui/ProgressBar';
import QuickStarter from './components/ui/QuickStarter';
import StockChart from './components/dashboard/StockChart';
import ProfileView from './components/views/ProfileView';
import SettingsView from './components/views/SettingsView';
import LandingView from './components/views/LandingView';
import AuthView from './components/views/AuthView';

export default function InvestmentAgentApp() {
    const [query, setQuery] = useState('');
    const [appState, setAppState] = useState('idle');
    const [viewState, setViewState] = useState('landing');
    const [progress, setProgress] = useState(0);
    const [activeLogs, setActiveLogs] = useState([]);
    const [isLogExpanded, setIsLogExpanded] = useState(true);
    const [showSettings, setShowSettings] = useState(false);
    const [showUserMenu, setShowUserMenu] = useState(false);
  
    // Gemini State
    const [aiSummary, setAiSummary] = useState('');
    const [isAiGenerating, setIsAiGenerating] = useState(false);
    const [chatInput, setChatInput] = useState('');
    const [chatHistory, setChatHistory] = useState([]);
    const [isChatLoading, setIsChatLoading] = useState(false);

    const logsEndRef = useRef(null);
    const chatEndRef = useRef(null);
    const userMenuRef = useRef(null);

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
    const startAnalysis = () => {
      if (!query) return;
      setAppState('processing');
      setProgress(0);
      setActiveLogs([]);
      setAiSummary('');

      // Simulation Sequence
      let step = 0;
      const interval = setInterval(() => {
        step++;
        setProgress((prev) => Math.min(prev + 15, 95));
      
        if (step < MOCK_LOGS.length + 1) {
          setActiveLogs(prev => [...prev, MOCK_LOGS[step - 1]]);
        }

        if (step >= MOCK_LOGS.length + 2) {
          clearInterval(interval);
          setProgress(100);
          setAppState('completed');
          // Trigger Gemini Analysis after simulation
          generateExecutiveSummary(); 
        }
      }, 800);
    };

    useEffect(() => {
      if (logsEndRef.current) {
        logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [activeLogs]);

    // Feature 1: Generate Executive Summary via Gemini
    const generateExecutiveSummary = async () => {
      setIsAiGenerating(true);
    
      // Construct context from our "Mock" data to simulate a real analysis result
      const contextPrompt = `
        角色：你是一名资深 A 股金融分析师 AI Agent。
        任务：根据以下（模拟的）股票数据，为投资者写一份简明扼要的"执行摘要"。
      
        股票代码：${query || '300750 (宁德时代)'}
        价格趋势：7天内从 ¥210 涨至 ¥235。
        市场情绪：75/100 (偏乐观)。
        关键事件：
        1. 海外储能订单落地 (置信度 0.88)
        2. 锂电池产能利用率回升
        3. 北向资金净流入
      
        要求：
        1. 语言风格专业、客观但有说服力，符合中国 A 股市场语境。
        2. 给出明确的"买入/持有/卖出"建议。
        3. 字数控制在 150 字以内。
        4. 使用中文回答。
      `;

      const summary = getMockResponse(contextPrompt);
      setAiSummary(summary);
      setIsAiGenerating(false);
    };

    // Feature 2: Chat / Follow-up
    const handleChatSubmit = async (e) => {
      e?.preventDefault();
      if (!chatInput.trim()) return;

      const userMsg = { role: 'user', text: chatInput };
      setChatHistory(prev => [...prev, userMsg]);
      setChatInput('');
      setIsChatLoading(true);

      const contextPrompt = `
        当前上下文：正在分析 ${query || '300750 (宁德时代)'} A股股票。
        已知信息：海外订单落地，股价震荡上行，北向资金流入。
        用户问题：${userMsg.text}
      
        请用简短、专业的 A 股金融术语回答用户问题。使用中文。
      `;

      const aiResponseText = getMockResponse(contextPrompt);

      setChatHistory(prev => [...prev, { role: 'ai', text: aiResponseText }]);
      setIsChatLoading(false);
    };

    const handleQuickStart = (text) => {
      setQuery(text);
    };

    const handleLogout = () => {
      setShowUserMenu(false);
      setViewState('landing');
      setAppState('idle');
      setQuery('');
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
          <AuthView viewState={viewState} setViewState={setViewState} />
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
                       className="w-8 h-8 rounded-full bg-gradient-to-br from-red-500 to-orange-600 border-2 border-slate-700 hover:border-red-500 transition-all flex items-center justify-center text-white text-sm font-bold shadow-lg"
                     >
                       ZL
                     </button>
                   
                     {/* User Dropdown Menu */}
                     {showUserMenu && (
                       <div className="absolute right-0 top-full mt-2 w-56 bg-slate-900/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 z-50">
                         {/* User Info */}
                         <div className="px-4 py-3 border-b border-white/10">
                           <p className="font-medium text-white">张磊</p>
                           <p className="text-xs text-slate-400">zhang.lei@example.com</p>
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
              {viewState === 'profile' && <ProfileView setViewState={setViewState} />}
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
                            <select className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-300">
                              <option>稳健型 (蓝筹/红利)</option>
                              <option>激进型 (题材/成长)</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">投资周期</label>
                            <select className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-300">
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
                     <AgentStatusNode icon={Globe} label="新闻分析" status={progress > 30 ? (progress > 60 ? 'done' : 'active') : 'pending'} />
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
                      <div className="p-4 h-48 overflow-y-auto font-mono text-xs md:text-sm space-y-2 bg-transparent">
                        {activeLogs.map((log, idx) => (
                          <div key={idx} className="flex gap-3 animate-in fade-in slide-in-from-left-2">
                            <span className="text-blue-400 w-24 shrink-0">[{log.agent}]</span>
                            <span className="text-slate-300">{log.text}</span>
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
                  <div className="md:col-span-8 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl relative overflow-hidden flex flex-col">
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
                         <div className="prose prose-invert prose-sm max-w-none text-slate-300 leading-relaxed whitespace-pre-wrap">
                           {aiSummary || "分析完成。正在等待 AI 生成报告..."}
                         </div>
                       )}
                     </div>

                     <div className="flex gap-4 mt-6 border-t border-white/10 pt-6 overflow-x-auto">
                       <div className="bg-slate-800/40 rounded-lg p-3 flex-1 border border-white/5 min-w-[100px]">
                         <p className="text-slate-500 text-xs uppercase font-bold mb-1">当前股价</p>
                         <p className="text-xl font-mono text-white">¥235.00</p>
                       </div>
                       <div className="bg-slate-800/40 rounded-lg p-3 flex-1 border border-white/5 min-w-[100px]">
                         <p className="text-slate-500 text-xs uppercase font-bold mb-1">压力位</p>
                         <p className="text-xl font-mono text-white">¥265.00</p>
                       </div>
                       <div className="bg-slate-800/40 rounded-lg p-3 flex-1 border border-white/5 min-w-[100px]">
                         <p className="text-slate-500 text-xs uppercase font-bold mb-1">止损位</p>
                         <p className="text-xl font-mono text-green-400">¥205.00</p>
                       </div>
                       <div className="bg-slate-800/40 rounded-lg p-3 flex-1 border border-white/5 min-w-[100px]">
                         <p className="text-slate-500 text-xs uppercase font-bold mb-1">风险等级</p>
                         <p className="text-xl font-mono text-yellow-400">Medium</p>
                       </div>
                     </div>
                  </div>

                  {/* 2. Sentiment/Metrics - Span 4 */}
                  <div className="md:col-span-4 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl flex flex-col justify-between">
                     <div>
                        <h3 className="text-sm font-bold text-slate-400 uppercase mb-4">市场情绪仪表盘</h3>
                        <div className="flex items-end gap-2 mb-2">
                           <span className="text-4xl font-bold text-red-500">75</span>
                           <span className="text-sm text-slate-500 mb-1">/ 100</span>
                        </div>
                        <p className="text-sm text-red-500 font-medium mb-6">偏向乐观 (Optimistic)</p>
                      
                        <div className="space-y-3">
                          <div>
                            <div className="flex justify-between text-xs text-slate-400 mb-1">
                              <span>新闻舆情</span>
                              <span className="text-red-400">+12%</span>
                            </div>
                            <div className="w-full bg-slate-800/50 h-1.5 rounded-full overflow-hidden">
                              <div className="bg-red-500 w-[80%] h-full rounded-full"></div>
                            </div>
                          </div>
                          <div>
                            <div className="flex justify-between text-xs text-slate-400 mb-1">
                              <span>主力资金 (净流出)</span>
                              <span className="text-green-400">-3%</span>
                            </div>
                            <div className="w-full bg-slate-800/50 h-1.5 rounded-full overflow-hidden">
                              <div className="bg-green-500 w-[45%] h-full rounded-full"></div>
                            </div>
                          </div>
                        </div>
                     </div>
                  </div>

                  {/* 3. Interactive Chart - Full Span */}
                  <StockChart data={MOCK_CHART_DATA} />

                  {/* 4. Citations - Span 7 */}
                  <div className="md:col-span-7 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl">
                     <h3 className="text-sm font-bold text-slate-400 uppercase mb-4 flex items-center gap-2">
                       <Database className="w-4 h-4" /> 
                       参考数据源 (RAG Retrieval)
                     </h3>
                     <div className="space-y-3">
                       {CITATIONS.map((cite, idx) => (
                         <a key={idx} href={cite.url} className="block group">
                           <div className="flex items-start justify-between p-3 rounded-lg hover:bg-white/5 transition-colors border border-transparent hover:border-white/10">
                              <div className="flex gap-3">
                                 <div className="mt-1">
                                   <FileText className="w-4 h-4 text-slate-500 group-hover:text-blue-400" />
                                 </div>
                                 <div>
                                   <p className="text-sm font-medium text-slate-300 group-hover:text-white transition-colors">{cite.title}</p>
                                   <p className="text-xs text-slate-500 mt-1">{cite.source} • {cite.date}</p>
                                 </div>
                              </div>
                              <ArrowRight className="w-4 h-4 text-slate-600 opacity-0 group-hover:opacity-100 transition-all -translate-x-2 group-hover:translate-x-0" />
                           </div>
                         </a>
                       ))}
                     </div>
                  </div>

                  {/* 5. Chat with Gemini (New Feature) - Span 5 */}
                  <div className="md:col-span-5 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-xl overflow-hidden flex flex-col h-[320px]">
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
