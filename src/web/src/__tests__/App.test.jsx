import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from '../App';

// Mock API客户端
vi.mock('../services/apiClient', () => ({
  getAuthToken: vi.fn(() => null),
  setAuthToken: vi.fn(),
  fetchProfile: vi.fn(() => Promise.reject(new Error('Not authenticated'))),
}));

describe('App Component', () => {
  it('renders home page by default', () => {
    render(<App />);
    
    // 检查首页元素
    const heroText = screen.getByText(/AI 投资研究 Agent/i);
    expect(heroText).toBeInTheDocument();
  });

  it('has navigation buttons', () => {
    render(<App />);
    
    // 检查导航按钮
    const researchBtn = screen.getByRole('button', { name: '研究' });
    const historyBtn = screen.getByRole('button', { name: '历史' });
    const settingsBtn = screen.getByRole('button', { name: '设置' });
    
    expect(researchBtn).toBeInTheDocument();
    expect(historyBtn).toBeInTheDocument();
    expect(settingsBtn).toBeInTheDocument();
  });

  it('navigates to research page when clicking research button', () => {
    render(<App />);
    
    // 点击研究按钮
    const researchBtn = screen.getByRole('button', { name: '研究' });
    fireEvent.click(researchBtn);
    
    // 检查是否跳转到研究页面
    const textarea = screen.getByPlaceholderText('输入你想研究的投资问题');
    expect(textarea).toBeInTheDocument();
  });
});