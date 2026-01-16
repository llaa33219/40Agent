#!/usr/bin/env python3
"""
40Agent - AI Agent that can see and control VMs
Entry point with automatic uv environment setup
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
VENV_PATH = PROJECT_ROOT / ".venv"
UV_LOCK = PROJECT_ROOT / "uv.lock"


def check_uv_installed() -> bool:
    """Check if uv is installed"""
    try:
        subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_uv() -> None:
    """Install uv using the official installer"""
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
    """Setup the virtual environment and install dependencies"""
    print("🔧 Setting up environment...")

    # Create venv and sync dependencies using uv
    try:
        subprocess.run(
            ["uv", "sync"],
            cwd=PROJECT_ROOT,
            check=True,
        )
        print("✅ Environment ready")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to setup environment: {e}")
        sys.exit(1)


def get_venv_python() -> Path:
    """Get the path to the Python interpreter in the virtual environment"""
    if sys.platform == "win32":
        return VENV_PATH / "Scripts" / "python.exe"
    return VENV_PATH / "bin" / "python"


def run_in_venv() -> None:
    """Re-execute this script inside the virtual environment"""
    venv_python = get_venv_python()

    if not venv_python.exists():
        print("❌ Virtual environment Python not found")
        sys.exit(1)

    # Re-execute with the venv Python
    os.execv(str(venv_python), [str(venv_python), __file__, "--in-venv"] + sys.argv[1:])


def main() -> None:
    """Main entry point"""
    # Check if we're already in the venv
    in_venv = "--in-venv" in sys.argv

    if not in_venv:
        # First run: setup environment
        print("🤖 40Agent - AI VM Controller")
        print("=" * 40)

        # Check/install uv
        if not check_uv_installed():
            install_uv()
            # Re-check after installation
            if not check_uv_installed():
                print("❌ uv still not found after installation. Please restart your shell.")
                sys.exit(1)

        # Setup environment if needed
        venv_python = get_venv_python()
        if not venv_python.exists() or not UV_LOCK.exists():
            setup_environment()

        # Re-run in venv
        run_in_venv()
    else:
        # Remove the --in-venv flag from args
        sys.argv.remove("--in-venv")

        # Now we're in the venv, import and run the actual application
        from src.server.app import run_server

        run_server()


if __name__ == "__main__":
    main()
