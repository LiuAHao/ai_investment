#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""AI 投资分析系统启动器"""

import os
import re
import sys
import glob
import shutil
import subprocess
import argparse

# Vite 7 要求 Node.js ^20.19.0 || >=22.12.0
NODE_MIN_OK = (20, 19, 0)
NODE_MIN_22 = (22, 12, 0)


def parse_node_version(version_str: str) -> tuple | None:
    """解析 `v20.19.0` 为 (20, 19, 0)；解析失败返回 None"""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", version_str or "")
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def node_version_ok(ver: tuple) -> bool:
    """判断 Node 版本是否满足 Vite 7 要求"""
    if ver is None:
        return False
    # >=20.19.0
    if ver[0] == 20 and ver >= NODE_MIN_OK:
        return True
    # >=22.12.0
    if ver[0] > 22 or (ver[0] == 22 and ver >= NODE_MIN_22):
        return True
    return False


def node_bin_dirs() -> list:
    """收集候选 Node bin 目录：PATH 中已有的 + nvm + homebrew"""
    dirs: list = []

    # 1. PATH 中已存在的 node 可执行目录
    for cmd in ("node", "nodejs"):
        found = shutil.which(cmd)
        if found:
            dirs.append(os.path.dirname(os.path.abspath(found)))

    # 2. nvm 已安装版本（按版本号降序，优先新版）
    nvm_root = os.environ.get("NVM_DIR") or os.path.expanduser("~/.nvm")
    nvm_versions = []
    for vdir in glob.glob(os.path.join(nvm_root, "versions", "node", "v*")):
        ver = parse_node_version(os.path.basename(vdir))
        nvm_versions.append((ver, vdir))
    nvm_versions.sort(key=lambda x: x[0] or (0, 0, 0), reverse=True)
    for _, vdir in nvm_versions:
        bin_dir = os.path.join(vdir, "bin")
        if os.path.isfile(os.path.join(bin_dir, "node")):
            dirs.append(bin_dir)

    # 3. Homebrew node 版本（node@20 / node@22 / node@24 ...，按版本号降序）
    brew_dirs = []
    for brew in ("/opt/homebrew/opt", "/usr/local/opt", "/opt/homebrew/var/homebrew/linked"):
        for vdir in glob.glob(os.path.join(brew, "node@*")):
            ver = parse_node_version(os.path.basename(vdir))
            brew_dirs.append((ver, vdir))
    brew_dirs.sort(key=lambda x: x[0] or (0, 0, 0), reverse=True)
    for _, vdir in brew_dirs:
        bin_dir = os.path.join(vdir, "bin")
        if os.path.isfile(os.path.join(bin_dir, "node")):
            dirs.append(bin_dir)

    # 去重（保持顺序）
    seen = set()
    unique = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def find_compatible_node() -> str | None:
    """
    在所有候选 Node bin 目录中，返回第一个满足 Vite 7 要求的 bin 目录；
    找不到则返回 None。
    """
    for bin_dir in node_bin_dirs():
        node_path = os.path.join(bin_dir, "node")
        if not os.path.isfile(node_path):
            continue
        try:
            out = subprocess.run(
                [node_path, "--version"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except Exception:
            continue
        ver = parse_node_version(out)
        if node_version_ok(ver):
            return bin_dir
    return None


def start_backend(port: int | None = None):
    """启动后端API服务"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    api_main = os.path.join(project_root, "src", "api", "main.py")

    if not os.path.isfile(api_main):
        raise SystemExit(f"后端文件不存在: {api_main}")

    src_dir = os.path.join(project_root, "src")
    os.environ["PYTHONPATH"] = src_dir
    if port is not None:
        os.environ["FLASK_PORT"] = str(port)
    subprocess.run([sys.executable, api_main])


def start_frontend(api_url: str | None = None):
    """启动前端开发服务器（自动选择满足 Vite 7 的 Node 版本）"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(project_root, "src", "web")

    if not os.path.isdir(web_dir):
        raise SystemExit(f"前端目录不存在: {web_dir}")

    env = os.environ.copy()
    if api_url:
        env["VITE_API_BASE_URL"] = api_url

    # 1. 检查当前 PATH 中的 node 是否满足要求
    current_npm = shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.exe")
    current_node = shutil.which("node")

    def _check(node_cmd: str) -> bool:
        try:
            out = subprocess.run(
                [node_cmd, "--version"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            return node_version_ok(parse_node_version(out))
        except Exception:
            return False

    # 2. 当前 PATH 中的 npm 对应的 node 版本够用 → 直接用
    if current_node and _check(current_node):
        if current_npm:
            subprocess.run([current_npm, "run", "dev"], cwd=web_dir, env=env, check=True)
            return
        # 只有 node 没有 npm，走候选目录
        bin_dir = os.path.dirname(os.path.abspath(current_node))
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        subprocess.run(["npm", "run", "dev"], cwd=web_dir, env=env, check=True)
        return

    # 3. 当前版本不够 → 从 nvm / homebrew 中找兼容版本
    bin_dir = find_compatible_node()
    if bin_dir:
        current_ver = ""
        try:
            current_ver = subprocess.run(
                [current_node, "--version"], capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except Exception:
            pass
        print(f"检测到当前 Node 版本 {current_ver or '(未知)'} 不满足 Vite 7 要求")
        print(f"自动切换至: {bin_dir}")
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        subprocess.run(["npm", "run", "dev"], cwd=web_dir, env=env, check=True)
        return

    # 4. 找不到兼容版本 → 报错提示
    hint = "请安装 Node.js 20.19+ 或 22.12+（推荐使用 nvm: `nvm install 22 && nvm use 22`）"
    if current_npm:
        hint += f"\n当前 npm: {current_npm}"
    raise SystemExit(f"未找到兼容的 Node.js 版本。{hint}")


def main():
    parser = argparse.ArgumentParser(description="AI投资分析系统启动器")
    parser.add_argument("--backend", "-b", action="store_true", help="仅启动后端")
    parser.add_argument("--frontend", "-f", action="store_true", help="仅启动前端")
    parser.add_argument("--all", "-a", action="store_true", help="同时启动前后端")
    parser.add_argument("--port", type=int, default=None, help="后端端口，默认读取 FLASK_PORT 或使用 5001")
    parser.add_argument("--api-url", default=None, help="前端请求的后端地址，例如 http://localhost:5003")

    args = parser.parse_args()

    if args.all:
        print("注意：同时启动前后端需要打开两个终端")
        print("请在终端1运行: python run.py --backend --port 5003")
        print("请在终端2运行: python run.py --frontend --api-url http://localhost:5003")
        return

    if args.backend:
        start_backend(args.port)
    elif args.frontend:
        start_frontend(args.api_url)
    else:
        print("默认启动前端开发服务器...")
        start_frontend(args.api_url)


if __name__ == "__main__":
    main()
