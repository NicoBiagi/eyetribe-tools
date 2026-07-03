import os
import socket
import subprocess
import time
from pathlib import Path

DEFAULT_INSTALL_SERVER_EXE = Path(r"C:\Program Files (x86)\EyeTribe\Server\EyeTribe.exe")
BUNDLED_SERVER_EXE = Path(__file__).parent / "vendor" / "EyeTribe" / "Server" / "EyeTribe.exe"
ENV_SERVER_EXE = "EYETRIBE_SERVER_EXE"


def find_eyetribe_server(server_exe=None):
    candidates = []

    if server_exe is not None:
        candidates.append(Path(server_exe))

    env_path = os.environ.get(ENV_SERVER_EXE)
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(BUNDLED_SERVER_EXE)
    candidates.append(DEFAULT_INSTALL_SERVER_EXE)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "Could not find EyeTribe.exe. Searched:\n"
        f"{searched}\n\n"
        "Install Eye Tribe, bundle the server in eyetribe_tools/vendor/EyeTribe/Server, "
        f"or set the {ENV_SERVER_EXE} environment variable."
    )


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
    server_exe=None,
):
    server_path = find_eyetribe_server(server_exe=server_exe)

    if restart_existing:
        stop_eyetribe_server()

    elif is_eyetribe_server_running(port=port):
        print(f"Eye Tribe server is already running on port {port}.")
        return None

    args = [
        str(server_path),
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
        cwd=str(server_path.parent),
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
    print(f"Using server: {server_path}")
    return process