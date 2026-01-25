import os
import subprocess
import shutil

def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(project_root, "src", "web")

    if not os.path.isdir(web_dir):
        raise SystemExit(f"前端目录不存在: {web_dir}")

    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.exe")
    if not npm_cmd:
        raise SystemExit("未找到 npm，请确认已安装 Node.js 并配置到 PATH。")

    subprocess.run([npm_cmd, "run", "dev"], cwd=web_dir, check=True)


if __name__ == "__main__":
    main()
