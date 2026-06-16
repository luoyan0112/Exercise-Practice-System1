"""
英语刷题系统 - 主入口
后端与前端分离运行，关闭 GUI 不影响后端服务
"""
import sys
import os
import subprocess
import time
import socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

BACKEND_PORT = 8765
_backend_process = None


def _is_backend_running():
    """检测后端是否已在运行"""
    try:
        s = socket.create_connection(('127.0.0.1', BACKEND_PORT), timeout=0.5)
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def _start_backend():
    """启动后端服务"""
    global _backend_process
    _backend_process = subprocess.Popen(
        [sys.executable, '-m', 'backend.server'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
    )
    for _ in range(50):
        if _is_backend_running():
            print('[后端] API 服务已启动 (127.0.0.1:8765)')
            return True
        time.sleep(0.2)
    print('[后端] 启动超时')
    return False


def _stop_backend():
    """关闭本次启动的后端"""
    global _backend_process
    if _backend_process and _backend_process.poll() is None:
        if sys.platform == 'win32':
            _backend_process.kill()
        else:
            _backend_process.terminate()
        _backend_process.wait(timeout=3)
        print('[后端] 服务已关闭')


def main():
    already_running = _is_backend_running()

    if not already_running:
        print('[后端] 未检测到运行中的后端，正在启动...')
        if not _start_backend():
            import tkinter.messagebox as mb
            mb.showerror('启动失败',
                '后端 API 服务启动失败。\n'
                '可尝试手动启动：python -m backend.server')
            return

    try:
        from frontend.gui import main as gui_main
        gui_main()
    finally:
        # 打印后端信息，不自动关闭
        if _is_backend_running():
            print('\n========================================')
            print('  后端 API 服务仍在运行中')
            print('  地址: http://127.0.0.1:8765')
            print('  如需关闭: 在终端中按 Ctrl+C')
            if not already_running and _backend_process:
                print('  或按 Y 关闭后端 (按 N 保持运行)')
                try:
                    choice = input('  [Y/n]: ').strip().lower()
                    if choice in ('', 'y', 'yes'):
                        _stop_backend()
                        print('  后端已关闭')
                except:
                    _stop_backend()
            print('========================================\n')
        else:
            print('\n[后端] 后端服务未运行')
            print('下次启动前端前需手动启动: python -m backend.server')


if __name__ == '__main__':
    main()
