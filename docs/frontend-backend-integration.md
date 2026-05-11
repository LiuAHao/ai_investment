# 前后端集成文档

## 概述

本文档描述了AI投资分析系统前后端集成的实现细节。

## 功能特性

### 1. V2功能启用

V2功能通过环境变量 `AGENT_V2_ENABLED=true` 启用。

### 2. 反馈系统

#### Toast通知
- 成功提示（绿色）
- 错误提示（红色）
- 警告提示（黄色）
- 信息提示（蓝色）

#### 加载状态
- 按钮加载状态
- 页面加载状态
- 数据加载状态

#### 进度指示
- 进度条
- 步骤指示器
- 加载动画

#### 表单验证
- 实时验证提示
- 错误字段高亮
- 验证消息显示

## API端点

### V2 API
- `POST /api/agent/v2/query` - V2查询接口
- `GET /api/agent/v2/status/<task_id>` - 任务状态查询
- `GET /api/agent/v2/session/<session_id>` - 获取会话详情
- `GET /api/agent/v2/health` - V2健康检查
- `GET /api/agent/v2/events/<task_id>` - SSE实时事件流

### 用户管理
- `GET /api/user/profile` - 获取用户信息
- `PUT /api/user/profile` - 更新用户信息
- `PUT /api/user/phone` - 更新手机号
- `PUT /api/user/password` - 更新密码
- `GET /api/user/quota` - 获取配额使用情况
- `GET /api/user/tiers` - 获取所有等级信息
- `POST /api/user/upgrade` - 升级用户等级

### 股票数据
- `GET /api/stock/analyze` - 股票分析
- `GET /api/stock/technical` - 技术指标
- `GET /api/stock/history` - 历史行情
- `GET /api/stock/summary` - 股票汇总

### 新闻数据
- `GET /api/news/titles` - 获取新闻标题
- `POST /api/news/filter` - 按关键词筛选新闻
- `POST /api/news/relevant` - 获取相关新闻

### 聊天功能
- `POST /api/chat/send` - 发送消息
- `GET /api/chat/history` - 获取聊天历史
- `GET /api/chat/sessions` - 获取聊天会话列表
- `DELETE /api/chat/clear` - 清空聊天历史
- `POST /api/chat/ask` - 简短问答

## 测试

### 后端测试
```bash
python -m pytest tests/ -v
```

### 前端测试
```bash
cd src/web && npm run test
```

### 集成测试
```bash
python -m pytest tests/test_integration.py tests/test_e2e.py -v
```

## 故障排除

### V2功能未启用
检查 `.env` 文件中是否设置了 `AGENT_V2_ENABLED=true`。

### API连接失败
确保后端服务正在运行：`python run.py --backend`

### 前端构建失败
检查Node.js版本和依赖：`cd src/web && npm install`

### 测试失败
确保所有服务正在运行，并检查测试环境配置。