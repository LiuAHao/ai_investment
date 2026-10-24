#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试环境默认关闭运行观测，避免写入真实 observability.sqlite。"""

import os

os.environ.setdefault("OBS_ENABLED", "0")
