# utils 模块简介

utils 模块用于提供后端通用工具能力，当前包含认证与联网搜索相关功能。

## 目录与职责

- jwt_utils.py：JWT 生成与解码
- web_search.py：联网搜索封装（支持区域与代理控制）

## 联网搜索说明

`search_web(query, max_results=5, region=None)` 用于检索外部信息，默认使用中文区域（cn-zh）。

可用环境变量：

- DDGS_REGION：覆盖默认区域
- DDGS_DISABLE_PROXY=1：临时禁用代理以减少地区偏差

## 认证说明

`jwt_utils.py` 提供 `create_access_token` 与 `decode_access_token`，用于用户登录态管理。
