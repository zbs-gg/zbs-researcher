"""Private, atomic receipts and cross-process serialization for --fire."""
import json
import os
import threading
import time
from pathlib import Path


_LOCK_STALE_SECONDS = 900


def read_response_with_deadline(response, timeout, *, monotonic=time.monotonic):
    """Read an HTTP response under one total wall-clock deadline.

    ``urllib``'s timeout is a per-blocking-operation socket timeout. A server
    can therefore keep a response alive indefinitely by sending occasional
    bytes. Reading in a daemon thread lets the caller enforce one portable
    deadline without signals or platform-specific process primitives. Closing
    the response on expiry also asks the blocked socket read to stop.
    """
    timeout = float(timeout)
    if timeout <= 0:
        raise ValueError("HTTP deadline must be greater than zero")
    deadline = monotonic() + timeout
    completed = threading.Event()
    result = {}

    def read_body():
        try:
            result["body"] = response.read()
        except BaseException as exc:  # propagate the reader's original error
            result["error"] = exc
        finally:
            completed.set()

    reader = threading.Thread(target=read_body, daemon=True)
    reader.start()
    remaining = max(0.0, deadline - monotonic())
    if not completed.wait(remaining):
        try:
            response.close()
        except Exception:
            pass
        raise TimeoutError(
            f"HTTP total wall-clock deadline exceeded after {timeout:g} seconds"
        )
    if "error" in result:
        raise result["error"]
    return result.get("body", b"")


def acquire_run_lock(out_dir):
    """Hold one portable atomic-directory lock for the whole connector call.

    mkdir is atomic on the filesystems supported by the project. A lock left
    by a killed process becomes recoverable after fifteen minutes, longer than
    the connector's intended ten-minute network timeout.
    """
    lock_path = Path(out_dir) / ".fire.lock"
    while True:
        try:
            lock_path.mkdir(mode=0o700)
            return lock_path
        except FileExistsError:
            try:
                stale = time.time() - lock_path.stat().st_mtime
                if stale >= _LOCK_STALE_SECONDS:
                    lock_path.rmdir()
                    continue
            except (FileNotFoundError, OSError):
                continue
            time.sleep(0.05)


def release_run_lock(lock_path):
    if lock_path is None:
        return
    try:
        Path(lock_path).rmdir()
    except FileNotFoundError:
        pass


def write_private_json_atomic(path, payload):
    """Replace a JSON receipt atomically and keep it owner-readable only."""
    path = Path(path)
    tmp = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def write_private_text_atomic(path, text):
    """Atomically replace a UTF-8 text artifact with mode 0600."""
    path = Path(path)
    tmp = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(str(text))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
