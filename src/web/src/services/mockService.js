export const getMockResponse = (prompt) => {
  // Check if it's an executive summary request
  if (prompt.includes("执行摘要") || prompt.includes("投资者")) {
    return `基于多维度分析，宁德时代 (300750) 股价在过去一周呈现震荡上行态势，从 ¥210 升至 ¥235，涨幅达 11.9%。主要驱动因素包括锂电池产能利用率回升和新签海外大单预期。

**投资建议：买入**

市场情绪偏向乐观（75/100），北向资金持续净流入，机构评级维持"增持"。建议：
- 目标价位：¥265
- 止损设置：¥205
- 风险等级：中等

短期内关注创业板指数走势及电池级碳酸锂价格波动对成本端的影响。`;
  }
  
  // Check if it's a follow-up question
  if (prompt.includes("主力资金")) {
    return "根据东财Choice数据，主力资金今日呈现净流入态势（+3.5亿），其中超大单净流入占比最高。这表明机构资金在当前点位分歧减小，做多意愿增强。建议关注午后量能配合情况，若能持续放量，有望突破上方均线压制。";
  }
  
  if (prompt.includes("风险") || prompt.includes("波动")) {
    return "当前主要风险点：1) 下游新能源车销量不及预期；2) 原材料价格大幅波动；3) 行业竞争加剧导致毛利率承压。技术面上，上方 ¥240 一线存在套牢盘压力，需警惕冲高回落风险。建议控制仓位，不宜追高。";
  }
  
  // Default response for other questions
  return "基于当前A股市场环境及个股基本面，该标的展现出较好的韧性。建议结合大盘走势，采取低吸高抛策略。密切关注行业政策变化及公司最新公告。如有具体技术面或基本面问题，欢迎继续提问。";
};

export const MOCK_CHART_DATA = [
  { date: '01-20', price: 210, sentiment: 0.5, event: null },
  { date: '01-21', price: 215, sentiment: 0.6, event: null },
  { date: '01-22', price: 212, sentiment: 0.4, event: null },
  { date: '01-23', price: 225, sentiment: 0.8, event: null },
  { date: '01-24', price: 230, sentiment: 0.9, event: null },
  { date: '01-25', price: 228, sentiment: 0.7, event: null },
  { date: '01-26', price: 235, sentiment: 0.85, event: null },
];

export const MOCK_LOGS = [
  { agent: 'Orchestrator', text: '接收到任务：分析 300750 短期走势', status: 'done' },
  { agent: 'DataAgent', text: '连接 Wind/东方财富 API 获取 Level-2 行情...', status: 'done' },
  { agent: 'NewsAgent', text: '检索 财联社 & 证券时报 关键词 "宁德时代"', status: 'done' },
  { agent: 'NewsAgent', text: '检测到关键利好：海外储能订单落地 (置信度 0.88)', status: 'done' },
  { agent: 'RiskAgent', text: '计算 Beta 值... 相对创业板指波动率适中', status: 'done' },
  { agent: 'MasterAgent', text: '结合北向资金流向，生成 A 股策略报告...', status: 'done' },
];

export const CITATIONS = [
  { source: '财联社', title: '宁德时代获海外储能大单', url: '#', date: '2小时前' },
  { source: '证券时报', title: '锂电板块资金回流，机构看好明年排产', url: '#', date: '昨日' },
  { source: '东方财富网', title: '创业板指午后拉升，宁德时代涨超5%', url: '#', date: '3小时前' },
];
