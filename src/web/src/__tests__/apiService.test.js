import { describe, it, expect, vi, beforeEach } from 'vitest';
import { submitQuery, getTaskStatus, healthCheck } from '../services/apiV2Service';

// Mock apiClient
vi.mock('../services/apiClient', () => ({
  getAuthToken: vi.fn(() => 'mock-token'),
}));

// Mock fetch
global.fetch = vi.fn();

describe('API V2 Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('submits query successfully', async () => {
    const mockResponse = {
      task_id: 'task-123',
      session_id: 'session-456',
      status: 'processing',
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await submitQuery('测试查询');

    expect(result).toEqual(mockResponse);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/agent/v2/query'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
        body: expect.any(String),
      })
    );
  });

  it('handles query submission error', async () => {
    const mockError = {
      error: '查询失败',
    };

    fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => mockError,
    });

    await expect(submitQuery('测试查询')).rejects.toThrow('查询失败');
  });

  it('gets task status successfully', async () => {
    const mockStatus = {
      task_id: 'task-123',
      status: 'completed',
      result: { answer: '测试结果' },
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockStatus,
    });

    const result = await getTaskStatus('task-123');

    expect(result).toEqual(mockStatus);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/agent/v2/status/task-123'),
      expect.any(Object)
    );
  });

  it('performs health check successfully', async () => {
    const mockHealth = {
      status: 'ok',
      v2_enabled: true,
      version: '2.0.0',
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealth,
    });

    const result = await healthCheck();

    expect(result).toEqual(mockHealth);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/agent/v2/health'),
      expect.any(Object)
    );
  });
});
