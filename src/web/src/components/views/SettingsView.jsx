import React, { useState } from 'react';

const SettingsView = () => {
  const [settings, setSettings] = useState({
    riskPref: '稳健型',
    period: '三个月',
    debugMode: false,
    showTrace: false,
    defaultV2: true,
    notifications: true,
  });

  const toggle = (key) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = () => {};

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 32, letterSpacing: '-0.02em' }}>设置</h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24 }}>
        {/* 分析偏好 */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
            分析偏好
          </h3>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--text2)', marginBottom: 6 }}>
              默认风险偏好
            </label>
            <select
              value={settings.riskPref}
              onChange={e => setSettings(prev => ({ ...prev, riskPref: e.target.value }))}
              style={{ width: '100%' }}
            >
              {['保守型', '稳健型', '平衡型', '进取型', '激进型'].map(v => <option key={v}>{v}</option>)}
            </select>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--text2)', marginBottom: 6 }}>
              默认投资周期
            </label>
            <select
              value={settings.period}
              onChange={e => setSettings(prev => ({ ...prev, period: e.target.value }))}
              style={{ width: '100%' }}
            >
              {['一个月', '三个月', '半年', '一年', '三年'].map(v => <option key={v}>{v}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--text2)', margin: 0 }}>默认进入 V2 分析</label>
            <button className={`toggle ${settings.defaultV2 ? 'on' : ''}`} onClick={() => toggle('defaultV2')}>
              <div className="toggle-knob" />
            </button>
          </div>
        </div>

        {/* 开发者选项 */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
            开发者选项
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--text2)', margin: 0 }}>调试模式</label>
            <button className={`toggle ${settings.debugMode ? 'on' : ''}`} onClick={() => toggle('debugMode')}>
              <div className="toggle-knob" />
            </button>
            <span style={{ fontSize: 12, color: 'var(--text3)' }}>开启后可查看原始 trace 和工具参数</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--text2)', margin: 0 }}>显示完整 Agent Trace</label>
            <button className={`toggle ${settings.showTrace ? 'on' : ''}`} onClick={() => toggle('showTrace')}>
              <div className="toggle-knob" />
            </button>
          </div>
        </div>

        {/* 通知 */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
            通知
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--text2)', margin: 0 }}>研究完成通知</label>
            <button className={`toggle ${settings.notifications ? 'on' : ''}`} onClick={() => toggle('notifications')}>
              <div className="toggle-knob" />
            </button>
          </div>
        </div>
      </div>

      {/* Save button */}
      <div style={{ marginTop: 32, display: 'flex', alignItems: 'center' }}>
        <button
          onClick={handleSave}
          style={{
            padding: '12px 32px', borderRadius: 8, fontSize: 15, fontWeight: 600,
            background: 'linear-gradient(135deg, var(--red), var(--orange))', color: '#fff',
          }}
        >
          保存设置
        </button>
      </div>
    </div>
  );
};

export default SettingsView;
