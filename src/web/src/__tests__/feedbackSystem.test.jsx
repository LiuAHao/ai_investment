import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { FeedbackProvider, useFeedback } from '../contexts/FeedbackContext';
import ToastContainer from '../components/ui/ToastContainer';
import Toast from '../components/ui/Toast';
import LoadingButton from '../components/ui/LoadingButton';
import ProgressBar from '../components/ui/ProgressBar';

const TestComponent = () => {
  const { showSuccess, showError, setLoading, isLoading } = useFeedback();

  return (
    <div>
      <button onClick={() => showSuccess('成功消息')}>显示成功</button>
      <button onClick={() => showError('错误消息')}>显示错误</button>
      <button onClick={() => setLoading('test', true)}>设置加载</button>
      <button onClick={() => setLoading('test', false)}>取消加载</button>
      {isLoading('test') && <div>加载中...</div>}
    </div>
  );
};

describe('Feedback System', () => {
  it('provides feedback context', () => {
    render(
      <FeedbackProvider>
        <TestComponent />
      </FeedbackProvider>
    );

    expect(screen.getByText('显示成功')).toBeInTheDocument();
    expect(screen.getByText('显示错误')).toBeInTheDocument();
  });

  it('shows success toast', async () => {
    render(
      <FeedbackProvider>
        <TestComponent />
        <ToastContainer />
      </FeedbackProvider>
    );

    fireEvent.click(screen.getByText('显示成功'));

    expect(screen.getByText('成功消息')).toBeInTheDocument();
  });

  it('shows error toast', async () => {
    render(
      <FeedbackProvider>
        <TestComponent />
        <ToastContainer />
      </FeedbackProvider>
    );

    fireEvent.click(screen.getByText('显示错误'));

    expect(screen.getByText('错误消息')).toBeInTheDocument();
  });

  it('manages loading state', async () => {
    render(
      <FeedbackProvider>
        <TestComponent />
      </FeedbackProvider>
    );

    fireEvent.click(screen.getByText('设置加载'));
    expect(screen.getByText('加载中...')).toBeInTheDocument();

    fireEvent.click(screen.getByText('取消加载'));
    expect(screen.queryByText('加载中...')).not.toBeInTheDocument();
  });
});

describe('Toast Component', () => {
  it('renders toast with message', () => {
    render(<Toast message="测试消息" type="info" />);

    expect(screen.getByText('测试消息')).toBeInTheDocument();
  });

  it('renders toast with different types', () => {
    const { rerender } = render(<Toast message="成功" type="success" />);
    expect(screen.getByText('✓')).toBeInTheDocument();

    rerender(<Toast message="错误" type="error" />);
    expect(screen.getByText('✗')).toBeInTheDocument();

    rerender(<Toast message="警告" type="warning" />);
    expect(screen.getByText('⚠')).toBeInTheDocument();

    rerender(<Toast message="信息" type="info" />);
    expect(screen.getByText('ℹ')).toBeInTheDocument();
  });
});

describe('LoadingButton Component', () => {
  it('renders button with text', () => {
    render(<LoadingButton>点击我</LoadingButton>);

    expect(screen.getByText('点击我')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(<LoadingButton loading={true}>点击我</LoadingButton>);

    expect(screen.getByText('加载中...')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('shows custom loading text', () => {
    render(<LoadingButton loading={true} loadingText="请稍候...">点击我</LoadingButton>);

    expect(screen.getByText('请稍候...')).toBeInTheDocument();
  });
});

describe('ProgressBar Component', () => {
  it('renders progress bar', () => {
    render(<ProgressBar progress={50} />);

    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('shows correct progress', () => {
    render(<ProgressBar progress={75} showPercentage={true} />);

    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('hides percentage when showPercentage is false', () => {
    render(<ProgressBar progress={50} showPercentage={false} />);

    expect(screen.queryByText('50%')).not.toBeInTheDocument();
  });
});
