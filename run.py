import os
import sys
import subprocess
import shutil
import argparse


def start_backend():
    """启动后端API服务"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    api_main = os.path.join(project_root, "src", "api", "main.py")

    if not os.path.isfile(api_main):
        raise SystemExit(f"后端文件不存在: {api_main}")

    os.environ["PYTHONPATH"] = project_root
    subprocess.run([sys.executable, api_main])


def start_frontend():
    """启动前端开发服务器"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(project_root, "src", "web")

    if not os.path.isdir(web_dir):
        raise SystemExit(f"前端目录不存在: {web_dir}")

    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.exe")
    if not npm_cmd:
        raise SystemExit("未找到 npm，请确认已安装 Node.js 并配置到 PATH。")

    subprocess.run([npm_cmd, "run", "dev"], cwd=web_dir, check=True)


def main():
    parser = argparse.ArgumentParser(description="AI投资分析系统启动器")
    parser.add_argument("--backend", "-b", action="store_true", help="仅启动后端")
    parser.add_argument("--frontend", "-f", action="store_true", help="仅启动前端")
    parser.add_argument("--all", "-a", action="store_true", help="同时启动前后端")

    args = parser.parse_args()

    if args.all:
        print("注意：同时启动前后端需要打开两个终端")
        print("请在终端1运行: python run.py --backend")
        print("请在终端2运行: python run.py --frontend")
        return

    if args.backend:
        start_backend()
    elif args.frontend:
        start_frontend()
    else:
        print("默认启动前端开发服务器...")
        start_frontend()


if __name__ == "__main__":
    main()
