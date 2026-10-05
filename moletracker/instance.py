"""Only the interactive application owns this data-directory lock."""
import os
from pathlib import Path


class InstanceLock:
    def __init__(self, root):
        root=Path(root).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
        self.file=None
        try:
            self.file=(root/'instance.lock').open('a+b')
            self.file.seek(0)
            if not self.file.read(1):self.file.write(b'0');self.file.flush()
            self.file.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            if self.file:self.file.close()
            raise ValueError('此资料目录已在另一窗口打开，请切换到已有窗口。') from exc

    def close(self):
        self.file.close()
