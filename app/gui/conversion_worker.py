from PySide6.QtCore import QObject, QThread, Signal

from app.apply import ApplyError, apply_playlist
from app.project import Playlist


class ApplyWorker(QObject):
    progress = Signal(int, int, str)  # current, total, message
    finished = Signal()
    error = Signal(str)

    def __init__(self, playlist: Playlist, ffmpeg_path: str):
        super().__init__()
        self._playlist = playlist
        self._ffmpeg_path = ffmpeg_path

    def run(self) -> None:
        try:
            apply_playlist(
                self._playlist,
                ffmpeg_path=self._ffmpeg_path,
                progress_cb=lambda i, total, msg: self.progress.emit(i, total, msg),
            )
        except ApplyError as exc:
            self.error.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - surface any unexpected failure to the UI
            self.error.emit(f"Unexpected error: {exc}")
            return
        self.finished.emit()


def run_apply_in_thread(playlist: Playlist, ffmpeg_path: str, parent=None):
    """Create and start a QThread running ApplyWorker. Returns (thread, worker).

    Caller is responsible for keeping references alive until finished/error fires,
    and for connecting to progress/finished/error signals before calling thread.start().
    """
    thread = QThread(parent)
    worker = ApplyWorker(playlist, ffmpeg_path)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)

    return thread, worker
