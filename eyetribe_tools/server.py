import socket
import subprocess
import time
from pathlib import Path

SERVER_EXE = Path(r"C:\Program Files (x86)\EyeTribe\Server\EyeTribe.exe")


def is_port_open(host="127.0.0.1", port=6555, timeout=0.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_eyetribe_server_running(host="127.0.0.1", port=6555):
    return is_port_open(host=host, port=port)


def wait_for_eyetribe_server(host="127.0.0.1", port=6555, timeout_seconds=8):
    start = time.time()

    while time.time() - start < timeout_seconds:
        if is_eyetribe_server_running(host=host, port=port):
            return True
        time.sleep(0.2)

    return False


def stop_eyetribe_server(wait_seconds=1.0):
    subprocess.run(
        ["taskkill", "/IM", "EyeTribe.exe", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )

    time.sleep(wait_seconds)


def start_eyetribe_server(
    framerate=60,
    port=6555,
    remote=False,
    hidden=True,
    restart_existing=True,
    wait_timeout_seconds=8,
):
    if not SERVER_EXE.exists():
        raise FileNotFoundError(f"Could not find Eye Tribe server at: {SERVER_EXE}")

    if restart_existing:
        stop_eyetribe_server()

    elif is_eyetribe_server_running(port=port):
        print(f"Eye Tribe server is already running on port {port}.")
        return None

    args = [
        str(SERVER_EXE),
        f"--framerate={framerate}",
        f"--port={port}",
        f"--remote={str(remote)}",
    ]

    creationflags = 0
    startupinfo = None

    if hidden:
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    process = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL if hidden else None,
        stderr=subprocess.DEVNULL if hidden else None,
        creationflags=creationflags,
        startupinfo=startupinfo,
    )

    if not wait_for_eyetribe_server(port=port, timeout_seconds=wait_timeout_seconds):
        raise RuntimeError(
            f"Eye Tribe server did not become reachable on 127.0.0.1:{port} "
            f"within {wait_timeout_seconds} seconds."
        )

    print(f"Eye Tribe server started at {framerate} Hz on port {port}.")
    return process