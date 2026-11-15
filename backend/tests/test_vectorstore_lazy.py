import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_importing_vectorstore_does_not_connect_to_chroma(tmp_path):
    """Worker boot must not touch ChromaDB (a Chroma stall must not block startup)."""
    chroma_dir = tmp_path / "chroma_should_not_exist"
    code = (
        "import sys, services.vectorstore as v;"
        "assert v._collection is None, 'collection created at import';"
        "assert 'chromadb' not in sys.modules, 'chromadb imported at import'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env={**os.environ, "CHROMA_DB_PATH": str(chroma_dir)},
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert not chroma_dir.exists()


@pytest.mark.skipif(
    not hasattr(os, "fork") or sys.platform == "darwin",
    reason="requires os.fork (Linux CI / Render)",
)
def test_importing_then_forking_leaves_chroma_usable_in_the_child(tmp_path):
    """Preload-style scenario: import the module, fork, use Chroma in the child.

    With an eagerly created client (the old behaviour) the child hangs forever in
    collection.count(), which is the production symptom. With lazy initialisation
    nothing is created before the fork, so the child connects normally.
    """
    code = (
        "import os, sys, time, signal\n"
        "import services.vectorstore as v\n"
        "pid = os.fork()\n"
        "if pid == 0:\n"
        "    v.collection.count()\n"
        "    os._exit(0)\n"
        "deadline = time.time() + 30\n"
        "while time.time() < deadline:\n"
        "    done, status = os.waitpid(pid, os.WNOHANG)\n"
        "    if done:\n"
        "        sys.exit(0 if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0 else 1)\n"
        "    time.sleep(0.1)\n"
        "os.kill(pid, signal.SIGKILL)\n"
        "print('CHILD HUNG in collection.count()')\n"
        "sys.exit(2)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env={**os.environ, "CHROMA_DB_PATH": str(tmp_path / "chroma")},
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode == 0, result.stdout + result.stderr

def test_using_chroma_from_a_different_process_fails_fast(monkeypatch):
    """A client initialised before a fork must raise, never hang."""
    import services.vectorstore as vectorstore

    monkeypatch.setattr(vectorstore, "_collection", object())
    monkeypatch.setattr(vectorstore, "_owner_pid", os.getpid() + 1)

    with pytest.raises(RuntimeError, match="before a process fork"):
        vectorstore._get_collection()