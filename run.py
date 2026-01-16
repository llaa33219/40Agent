#!/usr/bin/env python3
"""
40Agent - AI Agent that can see and control VMs
Entry point with automatic uv environment setup and VM management
"""

import os
import subprocess
import sys
import signal
import time
import atexit
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
VENV_PATH = PROJECT_ROOT / ".venv"
UV_LOCK = PROJECT_ROOT / "uv.lock"
VM_DATA_DIR = PROJECT_ROOT / "vm_data"

VM_NAME = os.environ.get("VM_NAME", "40agent-vm")
QMP_SOCKET = os.environ.get("VM_QMP_SOCKET", f"/tmp/qemu-{VM_NAME}-qmp.sock")
VM_DISK = VM_DATA_DIR / f"{VM_NAME}.qcow2"

qemu_process = None


def check_uv_installed() -> bool:
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_uv() -> None:
    print("📦 Installing uv...")
    try:
        subprocess.run(
            ["curl", "-LsSf", "https://astral.sh/uv/install.sh"],
            stdout=subprocess.PIPE,
            check=True,
        )
        result = subprocess.run(
            ["sh"],
            input=subprocess.run(
                ["curl", "-LsSf", "https://astral.sh/uv/install.sh"],
                capture_output=True,
                check=True,
            ).stdout,
            capture_output=True,
            check=True,
        )
        print("✅ uv installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install uv: {e}")
        print("Please install uv manually: https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)


def setup_environment() -> None:
    print("🔧 Setting up environment...")
    try:
        subprocess.run(["uv", "sync"], cwd=PROJECT_ROOT, check=True)
        print("✅ Environment ready")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to setup environment: {e}")
        sys.exit(1)


def get_venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_PATH / "Scripts" / "python.exe"
    return VENV_PATH / "bin" / "python"


def check_qemu_installed() -> bool:
    try:
        subprocess.run(["qemu-system-x86_64", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def find_iso_file() -> Path | None:
    iso_files = list(VM_DATA_DIR.glob("*.iso"))
    if iso_files:
        return iso_files[0]
    return None


def create_vm_disk(size_gb: int = 50) -> bool:
    print(f"💾 Creating VM disk: {VM_DISK} ({size_gb}GB)")
    try:
        subprocess.run(
            ["qemu-img", "create", "-f", "qcow2", str(VM_DISK), f"{size_gb}G"],
            check=True,
            capture_output=True,
        )
        print(f"✅ VM disk created: {VM_DISK}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create VM disk: {e}")
        return False


def is_vm_running() -> bool:
    return Path(QMP_SOCKET).exists()


def start_vm() -> subprocess.Popen | None:
    global qemu_process

    if is_vm_running():
        print(f"✅ VM already running (QMP: {QMP_SOCKET})")
        return None

    if not check_qemu_installed():
        print("⚠️  QEMU not installed. Running in demo mode.")
        print("   Install with: sudo pacman -S qemu-full")
        return None

    iso_file = None
    first_boot = False

    if not VM_DISK.exists():
        iso_file = find_iso_file()
        if iso_file:
            print(f"📀 Found ISO: {iso_file.name}")
            if not create_vm_disk(size_gb=50):
                return None
            first_boot = True
        else:
            print(f"⚠️  VM disk not found: {VM_DISK}")
            print(f"   Place an ISO file in {VM_DATA_DIR}/ to auto-create VM")
            print("   Running in demo mode (no VM)")
            return None

    print(f"🖥️  Starting VM: {VM_NAME}")

    Path(QMP_SOCKET).unlink(missing_ok=True)

    qemu_cmd = [
        "qemu-system-x86_64",
        "-name",
        VM_NAME,
        "-m",
        os.environ.get("VM_MEMORY", "16384"),  # 16GB RAM
        "-smp",
        os.environ.get("VM_CPUS", "2"),
        "-hda",
        str(VM_DISK),
        "-qmp",
        f"unix:{QMP_SOCKET},server,nowait",
        "-device",
        "virtio-vga,max_hostmem=268435456",  # 256MB VRAM
        "-usb",
        "-device",
        "usb-tablet",
        "-display",
        "gtk",
    ]

    if first_boot and iso_file:
        print(f"📀 Booting from ISO for installation...")
        qemu_cmd.extend(["-cdrom", str(iso_file), "-boot", "d"])

    qemu_process = subprocess.Popen(
        qemu_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(50):
        if Path(QMP_SOCKET).exists():
            print(f"✅ VM started (QMP: {QMP_SOCKET})")
            if first_boot:
                print("📝 Note: Complete OS installation, then restart to boot from disk")
            return qemu_process
        time.sleep(0.1)

    print("⚠️  VM started but QMP socket not ready")
    return qemu_process


def cleanup_vm():
    global qemu_process
    if qemu_process:
        print("\n🛑 Stopping VM...")
        qemu_process.terminate()
        try:
            qemu_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            qemu_process.kill()
        qemu_process = None


def run_in_venv() -> None:
    venv_python = get_venv_python()
    if not venv_python.exists():
        print("❌ Virtual environment Python not found")
        sys.exit(1)
    os.execv(str(venv_python), [str(venv_python), __file__, "--in-venv"] + sys.argv[1:])


def main() -> None:
    in_venv = "--in-venv" in sys.argv

    if not in_venv:
        print("🤖 40Agent - AI VM Controller")
        print("=" * 40)

        if not check_uv_installed():
            install_uv()
            if not check_uv_installed():
                print("❌ uv still not found after installation. Please restart your shell.")
                sys.exit(1)

        venv_python = get_venv_python()
        if not venv_python.exists() or not UV_LOCK.exists():
            setup_environment()

        run_in_venv()
    else:
        sys.argv.remove("--in-venv")

        atexit.register(cleanup_vm)
        signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

        start_vm()

        from src.server.app import run_server

        run_server()


if __name__ == "__main__":
    main()
