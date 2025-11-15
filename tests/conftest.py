import os
import sys


def _add_src_to_path() -> None:
    """Ensure the local src directory is importable when running pytest."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(repo_root, "src")
    if os.path.isdir(src_path) and src_path not in sys.path:
        try:
            __import__("stjlib")
        except ModuleNotFoundError:
            sys.path.insert(0, src_path)


_add_src_to_path()
