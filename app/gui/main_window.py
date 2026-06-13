from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app import project as project_module
from app.gui.conversion_worker import run_apply_in_thread
from app.project import Playlist, Project, Track

AUDIO_FILE_FILTER = "Audio Files (*.mp3 *.ogg *.wav *.flac *.m4a *.aac);;All Files (*)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFXIV Thunderdome Playlist Manager")
        self.resize(900, 600)

        self.project_path = project_module.default_project_path()
        self.project: Project = project_module.load(self.project_path)
        self._current_playlist_id: str | None = None
        self._thread = None
        self._worker = None

        self._build_ui()
        self._reload_playlist_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # ffmpeg path row
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(QLabel("ffmpeg path:"))
        self.ffmpeg_edit = QLineEdit(self.project.ffmpeg_path)
        self.ffmpeg_edit.editingFinished.connect(self._on_ffmpeg_path_changed)
        ffmpeg_row.addWidget(self.ffmpeg_edit)
        ffmpeg_browse = QPushButton("Browse...")
        ffmpeg_browse.clicked.connect(self._browse_ffmpeg_path)
        ffmpeg_row.addWidget(ffmpeg_browse)
        root_layout.addLayout(ffmpeg_row)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        splitter.addWidget(self._build_playlist_panel())
        splitter.addWidget(self._build_track_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

    def _build_playlist_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("Playlists"))

        self.playlist_list = QListWidget()
        self.playlist_list.currentItemChanged.connect(self._on_playlist_selected)
        layout.addWidget(self.playlist_list)

        button_row = QHBoxLayout()
        new_btn = QPushButton("New")
        new_btn.clicked.connect(self._new_playlist)
        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(self._rename_playlist)
        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._duplicate_playlist)
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete_playlist)
        for b in (new_btn, rename_btn, dup_btn, del_btn):
            button_row.addWidget(b)
        layout.addLayout(button_row)

        return panel

    def _build_track_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Target paths group
        target_group = QGroupBox("Target Paths")
        target_layout = QVBoxLayout(target_group)

        group_json_row = QHBoxLayout()
        group_json_row.addWidget(QLabel("Group JSON:"))
        self.group_json_edit = QLineEdit()
        self.group_json_edit.editingFinished.connect(self._on_group_json_changed)
        group_json_row.addWidget(self.group_json_edit)
        group_json_browse = QPushButton("Browse...")
        group_json_browse.clicked.connect(self._browse_group_json)
        group_json_row.addWidget(group_json_browse)
        target_layout.addLayout(group_json_row)

        scd_dir_row = QHBoxLayout()
        scd_dir_row.addWidget(QLabel("SCD Folder:"))
        self.scd_dir_edit = QLineEdit()
        self.scd_dir_edit.editingFinished.connect(self._on_scd_dir_changed)
        scd_dir_row.addWidget(self.scd_dir_edit)
        scd_dir_browse = QPushButton("Browse...")
        scd_dir_browse.clicked.connect(self._browse_scd_dir)
        scd_dir_row.addWidget(scd_dir_browse)
        scd_dir_auto = QPushButton("Auto (sound/mylist)")
        scd_dir_auto.clicked.connect(self._auto_scd_dir)
        scd_dir_row.addWidget(scd_dir_auto)
        target_layout.addLayout(scd_dir_row)

        layout.addWidget(target_group)

        # Track list
        layout.addWidget(QLabel("Tracks (in playback order)"))
        self.track_list = QListWidget()
        self.track_list.setDragDropMode(QListWidget.InternalMove)
        self.track_list.model().rowsMoved.connect(self._on_tracks_reordered)
        layout.addWidget(self.track_list)

        track_button_row = QHBoxLayout()
        add_btn = QPushButton("Add Files...")
        add_btn.clicked.connect(self._add_tracks)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_track)
        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(self._rename_track)
        for b in (add_btn, remove_btn, rename_btn):
            track_button_row.addWidget(b)
        layout.addLayout(track_button_row)

        # Apply controls
        self.apply_btn = QPushButton("Apply Playlist")
        self.apply_btn.clicked.connect(self._apply_playlist)
        layout.addWidget(self.apply_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        layout.addWidget(self.progress_bar)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        layout.addWidget(self.log_view)

        return panel

    # ------------------------------------------------------------------
    # Playlist list management
    # ------------------------------------------------------------------
    def _reload_playlist_list(self) -> None:
        self.playlist_list.blockSignals(True)
        self.playlist_list.clear()
        for pid, playlist in self.project.playlists.items():
            item = QListWidgetItem(playlist.name)
            item.setData(Qt.UserRole, pid)
            self.playlist_list.addItem(item)
        self.playlist_list.blockSignals(False)

        if self.project.playlists:
            target_pid = self.project.active_playlist or next(iter(self.project.playlists))
            self._select_playlist_by_id(target_pid)
        else:
            self._current_playlist_id = None
            self._reload_track_list()
            self._reload_target_paths()

    def _select_playlist_by_id(self, pid: str) -> None:
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item.data(Qt.UserRole) == pid:
                self.playlist_list.setCurrentItem(item)
                return

    def _current_playlist(self) -> Playlist | None:
        if self._current_playlist_id is None:
            return None
        return self.project.playlists.get(self._current_playlist_id)

    def _on_playlist_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self._current_playlist_id = None
        else:
            self._current_playlist_id = current.data(Qt.UserRole)
            self.project.active_playlist = self._current_playlist_id
        self._reload_track_list()
        self._reload_target_paths()

    def _new_playlist(self) -> None:
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if not ok or not name.strip():
            return
        pid = self.project.add_playlist(name.strip())
        self._reload_playlist_list()
        self._select_playlist_by_id(pid)
        self._save_project()

    def _rename_playlist(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Playlist", "Playlist name:", text=playlist.name)
        if not ok or not name.strip():
            return
        playlist.name = name.strip()
        self._reload_playlist_list()
        self._save_project()

    def _duplicate_playlist(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        new_playlist = Playlist.from_dict(playlist.to_dict())
        new_playlist.name = f"{playlist.name} (copy)"
        pid = self.project.add_playlist(new_playlist.name)
        self.project.playlists[pid] = new_playlist
        self._reload_playlist_list()
        self._select_playlist_by_id(pid)
        self._save_project()

    def _delete_playlist(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        confirm = QMessageBox.question(
            self, "Delete Playlist", f"Delete playlist '{playlist.name}'?"
        )
        if confirm != QMessageBox.Yes:
            return
        del self.project.playlists[self._current_playlist_id]
        if self.project.active_playlist == self._current_playlist_id:
            self.project.active_playlist = None
        self._current_playlist_id = None
        self._reload_playlist_list()
        self._save_project()

    # ------------------------------------------------------------------
    # Target path fields
    # ------------------------------------------------------------------
    def _reload_target_paths(self) -> None:
        playlist = self._current_playlist()
        self.group_json_edit.blockSignals(True)
        self.scd_dir_edit.blockSignals(True)
        if playlist is None:
            self.group_json_edit.setText("")
            self.scd_dir_edit.setText("")
            self.group_json_edit.setEnabled(False)
            self.scd_dir_edit.setEnabled(False)
        else:
            self.group_json_edit.setEnabled(True)
            self.scd_dir_edit.setEnabled(True)
            self.group_json_edit.setText(playlist.target_group_json)
            self.scd_dir_edit.setText(playlist.target_scd_dir)
        self.group_json_edit.blockSignals(False)
        self.scd_dir_edit.blockSignals(False)

    def _on_group_json_changed(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        playlist.target_group_json = self.group_json_edit.text().strip()
        self._save_project()

    def _on_scd_dir_changed(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        playlist.target_scd_dir = self.scd_dir_edit.text().strip()
        self._save_project()

    def _browse_group_json(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Penumbra Group JSON", playlist.target_group_json, "JSON Files (*.json)"
        )
        if path:
            playlist.target_group_json = path
            self._reload_target_paths()
            self._save_project()

    def _browse_scd_dir(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        path = QFileDialog.getExistingDirectory(self, "Select SCD Folder", playlist.target_scd_dir)
        if path:
            playlist.target_scd_dir = path
            self._reload_target_paths()
            self._save_project()

    def _auto_scd_dir(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        if not playlist.target_group_json:
            QMessageBox.warning(self, "Auto SCD Folder", "Set the Group JSON path first.")
            return
        mod_root = os.path.dirname(playlist.target_group_json)
        playlist.target_scd_dir = os.path.join(mod_root, "sound", "mylist")
        self._reload_target_paths()
        self._save_project()

    # ------------------------------------------------------------------
    # Track list management
    # ------------------------------------------------------------------
    def _reload_track_list(self) -> None:
        self.track_list.blockSignals(True)
        self.track_list.clear()
        playlist = self._current_playlist()
        if playlist is not None:
            for track in playlist.tracks:
                item = QListWidgetItem(track.display_name)
                item.setData(Qt.UserRole, track)
                self.track_list.addItem(item)
        self.track_list.blockSignals(False)

    def _add_tracks(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            QMessageBox.information(self, "Add Files", "Create or select a playlist first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Audio Files", "", AUDIO_FILE_FILTER)
        for path in paths:
            display_name = os.path.splitext(os.path.basename(path))[0]
            playlist.tracks.append(Track(source_path=path, display_name=display_name))
        if paths:
            self._reload_track_list()
            self._save_project()

    def _remove_track(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        row = self.track_list.currentRow()
        if row < 0:
            return
        del playlist.tracks[row]
        self._reload_track_list()
        self._save_project()

    def _rename_track(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        row = self.track_list.currentRow()
        if row < 0:
            return
        track = playlist.tracks[row]
        name, ok = QInputDialog.getText(self, "Rename Track", "Display name:", text=track.display_name)
        if not ok or not name.strip():
            return
        track.display_name = name.strip()
        self._reload_track_list()
        self._save_project()

    def _on_tracks_reordered(self, *args) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            return
        new_order: list[Track] = []
        for i in range(self.track_list.count()):
            track = self.track_list.item(i).data(Qt.UserRole)
            new_order.append(track)
        playlist.tracks = new_order
        self._save_project()

    # ------------------------------------------------------------------
    # ffmpeg path
    # ------------------------------------------------------------------
    def _on_ffmpeg_path_changed(self) -> None:
        self.project.ffmpeg_path = self.ffmpeg_edit.text().strip() or "ffmpeg"
        self._save_project()

    def _browse_ffmpeg_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select ffmpeg executable")
        if path:
            self.project.ffmpeg_path = path
            self.ffmpeg_edit.setText(path)
            self._save_project()

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def _apply_playlist(self) -> None:
        playlist = self._current_playlist()
        if playlist is None:
            QMessageBox.information(self, "Apply Playlist", "Create or select a playlist first.")
            return
        if not playlist.tracks:
            QMessageBox.information(self, "Apply Playlist", "Add at least one track first.")
            return
        if not playlist.target_group_json or not playlist.target_scd_dir:
            QMessageBox.warning(self, "Apply Playlist", "Set both the Group JSON and SCD Folder paths.")
            return

        self.log_view.clear()
        self.progress_bar.setRange(0, max(len(playlist.tracks), 1))
        self.progress_bar.setValue(0)
        self.apply_btn.setEnabled(False)

        self._thread, self._worker = run_apply_in_thread(playlist, self.project.ffmpeg_path, parent=self)
        self._worker.progress.connect(self._on_apply_progress)
        self._worker.finished.connect(self._on_apply_finished)
        self._worker.error.connect(self._on_apply_error)
        self._thread.start()

    def _on_apply_progress(self, current: int, total: int, message: str) -> None:
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(current)
        self.log_view.appendPlainText(message)

    def _on_apply_finished(self) -> None:
        self.apply_btn.setEnabled(True)
        self.log_view.appendPlainText("Apply complete.")
        self._save_project()

    def _on_apply_error(self, message: str) -> None:
        self.apply_btn.setEnabled(True)
        self.log_view.appendPlainText(f"ERROR: {message}")
        QMessageBox.critical(self, "Apply Failed", message)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save_project(self) -> None:
        project_module.save(self.project_path, self.project)

    def closeEvent(self, event) -> None:
        self._save_project()
        super().closeEvent(event)
