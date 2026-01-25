# AGENTS.md - AI投资分析系统开发指南

## 项目概述

这是一个基于多智能体架构的AI投资分析系统，采用Python后端（FastAPI/Flask）与React前端的混合架构。系统使用模块化Agent设计，包括数据获取Agent、新闻分析Agent、主控Agent和决策Agent。

## AI助手特殊指令

1. **保持用中文回答** - 所有回复和代码注释均使用中文
2. **禁止生成说明和日志文档** - 除非明确要求，否则不创建.md说明文档
3. **禁止生成测试代码** - 除非存在专门的测试文件夹或明确要求，否则不编写测试代码

## 构建和测试命令

### Python后端
```bash
# 安装依赖
pip install -r requirements.txt

# 运行主应用
python run.py

# 运行单个测试文件
python -m pytest src/agent/test_master_agent.py -v
python src/agent/test_master_agent.py

# 运行所有测试
python -m pytest tests/ -v
```

### React前端 (src/web目录)
```bash
# 进入前端目录
cd src/web

# 安装依赖
npm install

# 开发模式
npm run dev

# 构建
npm run build

# Lint检查
npm run lint

# 预览构建结果
npm run preview
```

## 代码风格指南

### Python代码风格

#### 导入规范
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模块说明文档
简述模块功能和用途
"""

# 标准库导入
import os
import sys
from typing import Dict, Optional, List

# 第三方库导入
import requests
import pandas as pd

# 本地模块导入
from agent.news_agent import NewsAgent
from stock.stock_api import get_stock_data
```

#### 命名约定
- **类名**: PascalCase (例: `MasterAgent`, `NewsItem`)
- **函数/变量名**: snake_case (例: `fetch_titles`, `stock_data`)
- **常量**: UPPER_SNAKE_CASE (例: `DEFAULT_SOURCES`)
- **私有方法**: 前缀下划线 (例: `_normalize_symbol`)

#### 文档字符串
```python
def fetch_titles(self, limit: int = 100) -> List[str]:
    """
    拉取多个RSS源并返回标题列表
    
    Args:
        limit: 最多返回标题数量
        
    Returns:
        标题列表
        
    Raises:
        ValueError: 当limit为负数时
    """
    pass
```

#### 类型提示
- 所有函数必须包含类型提示
- 使用 `typing` 模块的类型注解
- 可选参数使用 `Optional[Type]`

#### 错误处理
```python
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"操作失败: {e}")
    return default_value
except Exception as e:
    logger.error(f"未知错误: {e}")
    raise
```

### React/JavaScript代码风格

#### 组件结构
```jsx
import React, { useState, useEffect } from 'react';
import { Search, Cpu } from 'lucide-react';
import { LineChart, Line } from 'recharts';

const CustomComponent = ({ prop1, prop2 }) => {
  const [state, setState] = useState(null);
  
  useEffect(() => {
    // 副作用逻辑
  }, [dependencies]);
  
  const handleClick = () => {
    // 事件处理
  };
  
  return (
    <div className="component-wrapper">
      {/* JSX内容 */}
    </div>
  );
};

export default CustomComponent;
```

#### 命名约定
- **组件名**: PascalCase (例: `InvestmentAgentApp`)
- **变量/函数**: camelCase (例: `handleSubmit`, `isLoading`)
- **常量**: UPPER_SNAKE_CASE (例: `MOCK_DATA`)
- **CSS类**: kebab-case (例: `agent-status-node`)

#### JSX规范
- 使用Tailwind CSS类名
- 组件props使用解构
- 条件渲染使用三元运算符或逻辑AND
- 列表渲染添加key属性

## 项目结构说明

```
ai_investment/
├── src/
│   ├── agent/          # Agent模块
│   │   ├── master_agent.py      # 主控Agent
│   │   ├── news_agent.py        # 新闻Agent
│   │   ├── stock_agent.py       # 股票Agent
│   │   └── test_master_agent.py # 测试文件
│   ├── news/           # 新闻数据模块
│   │   ├── news_api.py
│   │   └── test_news_api.py
│   ├── stock/          # 股票数据模块
│   │   ├── stock_api.py
│   │   └── test_akshare_api.py
│   ├── web/            # React前端
│   │   ├── src/
│   │   │   ├── App.jsx
│   │   │   └── ...
│   │   ├── package.json
│   │   └── vite.config.js
├── requirements.txt    # Python依赖
├── run.py             # 主启动脚本
└── DESIGN.md          # 架构设计文档
```

## 开发工作流

### 添加新功能
1. 在相应模块下创建新文件
2. 遵循现有代码风格和命名约定
3. 添加适当的类型提示和文档字符串
4. 编写对应的测试文件
5. 运行lint和测试确保质量

### 修改现有代码
1. 先理解现有代码的上下文和依赖关系
2. 保持向后兼容性，如有破坏性变更需要更新调用处
3. 运行相关测试确保功能正常
4. 更新相关文档

## 测试策略

### Python测试
- 使用pytest框架
- 测试文件以`test_`开头
- 单元测试覆盖核心功能
- 集成测试验证Agent间交互

### 前端测试
- 使用ESLint进行代码检查
- 组件测试使用React Testing Library
- 端到端测试确保用户流程

## 性能优化

### Python后端
- 使用asyncio进行异步处理
- 实现适当的缓存机制
- 数据库查询优化
- 避免不必要的API调用

### React前端
- 使用React.memo防止不必要的重渲染
- 实现虚拟滚动处理大列表
- 图片懒加载
- 代码分割和懒加载

## 安全考虑

- API密钥使用环境变量，不硬编码
- 输入验证和清理
- 错误信息不暴露敏感信息
- 使用HTTPS进行通信
- 实施适当的访问控制

## 部署说明

### 开发环境
- Python 3.8+
- Node.js 16+
- npm或yarn

### 生产环境
- 使用Docker容器化部署
- 环境变量配置
- 日志收集和监控
- 数据库备份策略

## 常见问题解决

### 导入错误
- 确保Python路径正确设置
- 检查__init__.py文件是否存在
- 验证相对导入路径

### API调用失败
- 检查网络连接
- 验证API密钥和权限
- 实现重试机制
- 记录详细错误日志

### 前端构建错误
- 清除node_modules重新安装
- 检查Node.js版本兼容性
- 验证package.json依赖版本
- 运行eslint修复代码风格问题

## GitHub Copilot/Cursor 指令

已发现的特殊指令在 `.github/instructions/guide.instructions.md`:
1. 保持用中文回答
2. 若未说明生成说明和日志文档(.md),禁止生成说明和日志文档
3. 若没有专门的测试文件夹或未说明生成测试代码,禁止生成测试代码