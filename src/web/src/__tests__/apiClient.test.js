import { beforeEach, describe, expect, it, vi } from 'vitest';

const storage = {};
vi.stubGlobal('localStorage', {
  getItem: vi.fn(key => storage[key] || null),
  setItem: vi.fn((key, value) => {
    storage[key] = String(value);
  }),
  removeItem: vi.fn(key => {
    delete storage[key];
  }),
  clear: vi.fn(() => {
    Object.keys(storage).forEach(key => delete storage[key]);
  }),
});

const {
  fetchProfile,
  login,
  register,
  setAuthToken,
  updateProfile,
} = await import('../services/apiClient');

global.fetch = vi.fn();

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setAuthToken(null);
  });

  it('register serializes request body as JSON', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ token: 'token-1' }),
    });

    await register('alice', 'pass123', 'alice@example.com');

    const [, options] = fetch.mock.calls[0];
    expect(options.body).toBeTypeOf('string');
    expect(JSON.parse(options.body)).toEqual({
      username: 'alice',
      password: 'pass123',
      email: 'alice@example.com',
    });
  });

  it('login serializes request body as JSON', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ token: 'token-1' }),
    });

    await login('alice', 'pass123');

    const [, options] = fetch.mock.calls[0];
    expect(options.body).toBeTypeOf('string');
    expect(JSON.parse(options.body)).toEqual({
      username: 'alice',
      password: 'pass123',
    });
  });

  it('updateProfile serializes request body as JSON', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: '更新成功' }),
    });

    await updateProfile({ nickname: 'Alice', email: 'alice@example.com' });

    const [, options] = fetch.mock.calls[0];
    expect(options.body).toBeTypeOf('string');
    expect(JSON.parse(options.body)).toEqual({
      nickname: 'Alice',
      email: 'alice@example.com',
    });
  });

  it('fetchProfile sends authorization header when token exists', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ username: 'alice' }),
    });
    setAuthToken('token-1');

    await fetchProfile();

    const [, options] = fetch.mock.calls[0];
    expect(options.headers.Authorization).toBe('Bearer token-1');
  });

  it('register surfaces backend validation errors', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: '用户名或邮箱已存在' }),
    });

    await expect(register('alice', 'pass123', 'alice@example.com')).rejects.toThrow('用户名或邮箱已存在');
  });
});
