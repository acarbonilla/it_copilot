import hashlib
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .backup_contracts import BackupContractError


MAX_SNAPSHOT_BYTES = 1024 * 1024 * 1024
MAX_SNAPSHOT_SECONDS = 30 * 60
REQUIRED_OPTIONS = ("--single-transaction", "--quick", "--hex-blob", "--routines", "--events",
                    "--triggers", "--set-gtid-purged=OFF")


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_id: uuid.UUID
    path: Path
    size: int
    digest: str
    started_at: float
    completed_at: float


def create_mysql_snapshot(*, connection, executable, database, user, password, host, port, destination_root,
                          timeout=MAX_SNAPSHOT_SECONDS, max_bytes=MAX_SNAPSHOT_BYTES):
    """Create a consistent schema dump while a server-enforced global read lock excludes DDL and writes."""
    if timeout > MAX_SNAPSHOT_SECONDS or max_bytes > MAX_SNAPSHOT_BYTES or timeout <= 0 or max_bytes <= 0:
        raise BackupContractError("Snapshot limits are invalid")
    root = Path(destination_root).resolve(strict=True)
    snapshot_id = uuid.uuid4()
    final_path = root / f"{snapshot_id}.sql"
    started = time.time()
    option_path = output_path = None
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT @@version, @@default_storage_engine")
        _version, engine = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND ENGINE <> 'InnoDB'")
        if engine != "InnoDB" or cursor.fetchone()[0]:
            raise BackupContractError("Snapshot requires an all-InnoDB schema")
        cursor.execute("FLUSH TABLES WITH READ LOCK")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=root, prefix=".mysql-", suffix=".cnf",
                                         delete=False) as option_file:
            option_path = Path(option_file.name)
            option_file.write("[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n" % (user, password, host, port))
            option_file.flush(); os.fsync(option_file.fileno())
        os.chmod(option_path, stat_mode())
        with tempfile.NamedTemporaryFile("wb", dir=root, prefix=f".{snapshot_id}.", suffix=".partial",
                                         delete=False) as output:
            output_path = Path(output.name)
            command = [str(executable), f"--defaults-extra-file={option_path}", *REQUIRED_OPTIONS, database]
            process = subprocess.run(command, stdout=output, stderr=subprocess.PIPE, timeout=timeout, check=False,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            output.flush(); os.fsync(output.fileno())
        if process.returncode:
            raise BackupContractError("Database snapshot failed")
        size = output_path.stat().st_size
        if size <= 0 or size > max_bytes:
            raise BackupContractError("Database snapshot size limit exceeded")
        hasher = hashlib.sha256()
        with output_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
        digest = hasher.hexdigest()
        os.replace(output_path, final_path)
        output_path = None
        return SnapshotResult(snapshot_id, final_path, size, digest, started, time.time())
    except subprocess.TimeoutExpired:
        raise BackupContractError("Database snapshot timed out") from None
    finally:
        try: cursor.execute("UNLOCK TABLES")
        except Exception: pass
        cursor.close()
        for temporary in (option_path, output_path):
            if temporary is not None:
                try: temporary.unlink()
                except FileNotFoundError: pass


def stat_mode():
    return 0o600
