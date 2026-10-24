# AGENTS.md - AI投资分析系统开发指南

## AI助手特殊指令

1. **保持用中文回答** - 所有回复和代码注释均使用中文
2. **禁止生成说明和日志文档** - 除非明确要求,否则不创建.md说明文档
3. **禁止生成测试代码** - 除非存在专门的测试文件夹或明确要求,否则不编写测试代码

## 构建和测试命令

### Python后端
```bash
# 安装依赖（建议使用项目 venv）
.venv/bin/pip install -r requirements.txt

# 启动后端（默认端口 5001）
.venv/bin/python run.py --backend

# 启动前端开发服务器
.venv/bin/python run.py --frontend

# 验证后端可启动（导入检查）
PYTHONPATH=src .venv/bin/python -c "from api.main import create_app; create_app()"
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
from agents.orchestrator import OrchestratorAgent
from agents.state import Asset, AgentTask
from tools.registry import get_tool_registry
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
├── run.py              # 主启动脚本（前后端快捷启动，自动选择 Node 版本）
├── requirements.txt    # Python依赖
├── docs/               # 设计文档与历史记录
└── src/
    ├── agents/         # ★ 编排与质量层
    │   ├── pipeline.py         # 六层流水线（L0-L6）
    │   ├── orchestrator.py     # 对外入口
    │   ├── ledger.py           # 证据台账
    │   ├── debate.py           # 结构化辩论
    │   ├── judge.py            # 盲判 + 裁决
    │   ├── verifier.py         # 质检
    │   ├── base.py             # BaseReActAgent基类
    │   ├── loop.py             # ReAct循环执行器
    │   ├── state.py            # 状态模型
    │   ├── events.py           # 事件发射
    │   └── memory.py           # 会话记忆
    ├── analysts/       # 四路分析师（market/news/fundamental/macro）+ 注册表
    ├── memory/         # 决策落库 / 到期结算 / 反思回灌
    ├── backtest/       # 回测（PIT / T+1 / 校准指标）
    ├── api/            # Flask API
    │   ├── main.py
    │   ├── events.py   # SSE事件流
    │   └── routes/     # agent/history路由
    ├── asset/          # 资产主数据与解析
    ├── tools/          # 工具层（注册中心 + 20个工具）
    ├── data/           # 数据源（行情/财务/公告/宏观/新闻）
    ├── tests/          # 纯逻辑单测 + 离线端到端冒烟
    ├── services/       # 事件总线等
    ├── obs/            # 可观测性（运行记录 / 结构化日志 / 诊断接口）
    ├── utils/          # LLM客户端、PIT、联网搜索
    └── web/            # React前端（Vite）
```

## 开发工作流

### 添加新功能
1. 在相应模块下创建新文件
2. 遵循现有代码风格和命名约定
3. 添加适当的类型提示和文档字符串
4. 运行lint和测试确保质量

### 修改现有代码
1. 先理解现有代码的上下文和依赖关系
2. 保持向后兼容性,如有破坏性变更需要更新调用处
3. 运行相关测试确保功能正常

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

测试例外：`tests/` 与 `src/web/src/**/__tests__/` 已存在，修改相关逻辑时应在这些目录补充或更新测试。

## 提交与推送规范

本仓库为开源项目。以下规则长期有效，所有提交与推送默认遵守。

### 1. 基本原则

- `main` 始终保持可运行、可构建、可发布。
- 一次提交只做一件事：功能、修复、重构、文档不要混在一起。
- 不提交任何密钥、用户数据、运行日志、数据库、行情缓存、个人配置。
- 推送前必须完成本地验证；未验证的代码不进入 `main`。
- 不直接修改已推送的历史；需要改写历史时按第 8 节处理。

### 2. 提交前检查

```bash
git status --short
git diff --cached --name-only | rg '(^\.env$|sessions\.json|\.sqlite|\.db$|^logs/|quant_cache|\.commandcode/|docs/archive/|^src/stock/|^--full-page$)'
git diff --cached --check
git diff --cached --stat
```

敏感值扫描（只确认是否命中，不打印命中内容）：

```bash
rg -n --hidden -g '!.git' -g '!*.sqlite' -g '!.env' \
  'sk-[A-Za-z0-9]{16,}|APCA-API-KEY|ALPACA_API_KEY=[A-Za-z0-9]|TUSHARE_TOKEN=[A-Za-z0-9]' .
```

大文件检查（单文件超过 1MB 需在提交说明中解释，超过 10MB 禁止提交）：

```bash
git diff --cached --name-only | xargs -I{} du -k "{}" | awk '$1>1024'
```

### 3. 禁止提交清单

以下内容只保留在本地，不进入 Git：

- `.env`、任何真实密钥、Token、数据库连接串
- `src/data/sessions.json`
- `src/data/*.sqlite`、`*.db`、`ai_investment.db`
- `logs/`
- `src/data/quant_cache/`
- `src/data/capabilities.json`
- `.commandcode/`
- `docs/archive/`
- `src/stock/`（akshare 时代遗留，含第三方文档）
- `--full-page` 等临时截图
- `node_modules/`、`dist/`、`__pycache__/`

`.env.example` 可以提交，但只能包含占位值，例如 `your-deepseek-api-key`。

### 4. 推送前验证

后端：

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests -q
PYTHONPATH=src .venv/bin/python -c "from api.main import create_app; create_app()"
```

前端：

```bash
cd src/web
npm test -- --run
npm run build
```

只改文档时，至少运行 `git diff --check`，并确认没有夹带代码改动。

### 5. 分支命名

- 功能：`feat/<short-name>`
- 修复：`fix/<short-name>`
- 重构：`refactor/<short-name>`
- 文档：`docs/<short-name>`
- 实验：`exp/<short-name>`，不合并到 `main`

单人开发允许直接提交 `main`，但必须通过第 2、4 节检查。多人协作或大范围重构使用分支 + Pull Request。

### 6. Commit message

格式：

```text
<type>(<scope>): <subject>

<body>

<footer>
```

`type` 取值：`feat`、`fix`、`refactor`、`perf`、`docs`、`test`、`chore`、`build`、`ci`、`revert`。

`scope` 取值：`agents`、`analysts`、`pipeline`、`tools`、`data`、`web`、`obs`、`quant`、`backtest`、`docs`、`deps`。

要求：

- `subject` 不超过 50 个字符，祈使句，结尾不加句号。
- `body` 说明为什么改、改了什么、有什么影响；每行不超过 72 个字符。
- 破坏性变更在 footer 写 `BREAKING CHANGE: ...`。
- 关联 issue 写 `Refs #123`。
- 不写“update”“fix bug”“修改一下”这类无信息量的 subject。

示例：

```text
feat(pipeline): 增加按争议度触发辩论

多空双方各有 3 条以上论点时至少执行 1 轮，
争议度只决定 1 轮还是 2 轮。

Refs #42
```

### 7. 推送

- 推送前确认 `git status` 干净，暂存区只包含预期文件。
- 推送命令：`git push origin main` 或 `git push origin <branch>`。
- 不使用 `git push --force` 覆盖正常提交；需要撤销已推送提交时使用 `git revert`。
- 推送后确认远端 HEAD 与本地一致：`git ls-remote origin refs/heads/main`。

### 8. 密钥泄漏与历史改写

发现密钥、用户数据或数据库进入 Git 后：

1. 立即轮换对应密钥，不要只删文件。
2. 备份仓库：`git bundle create ../backup-$(date +%Y%m%d).bundle --all`。
3. 使用 `git filter-repo` 从全部历史移除敏感路径。
4. 强制推送并通知所有协作者重新 clone。
5. 若仓库曾公开，视密钥已泄漏处理：轮换是唯一有效补救。

历史改写属于不可逆操作，执行前必须备份并确认影响范围。

### 9. 版本与发布

- 里程碑使用语义化版本标签：`v4.0.0`、`v4.1.0`、`v4.1.1`。
- 发布说明从 commit 历史整理，至少包含：新增、修复、破坏性变更、升级步骤。
- 依赖升级单独提交，不与业务改动混合。

### 10. 提交信息中的 AI 协作

使用 AI 辅助生成的提交，按工具要求在 commit message 末尾保留协作声明。协作者应在提交前自行复核内容、密钥与测试结果。
