import os
import sys
import subprocess
import shutil
import argparse


def start_backend(port: int | None = None):
    """启动后端API服务"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    api_main = os.path.join(project_root, "src", "api", "main.py")

    if not os.path.isfile(api_main):
        raise SystemExit(f"后端文件不存在: {api_main}")

    os.environ["PYTHONPATH"] = project_root
    if port is not None:
        os.environ["FLASK_PORT"] = str(port)
    subprocess.run([sys.executable, api_main])


def start_frontend(api_url: str | None = None):
    """启动前端开发服务器"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(project_root, "src", "web")

    if not os.path.isdir(web_dir):
        raise SystemExit(f"前端目录不存在: {web_dir}")

    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.exe")
    if not npm_cmd:
        raise SystemExit("未找到 npm，请确认已安装 Node.js 并配置到 PATH。")

    env = os.environ.copy()
    if api_url:
        env["VITE_API_BASE_URL"] = api_url
    subprocess.run([npm_cmd, "run", "dev"], cwd=web_dir, env=env, check=True)


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
