# FFXIV Thunderdome Playlist Manager

Desktop app (Windows/Linux) for managing multiple in-game music "playlists" for
FFXIV mods built around a Penumbra `Single` option group that swaps
`sound/dam.scd`.

For each playlist you maintain an ordered list of source audio files (MP3, OGG,
WAV, FLAC, etc.). Clicking **Apply Playlist**:

1. Converts each track to FFXIV's `.scd` format (normalizes audio via `ffmpeg` to
   44.1kHz stereo Vorbis, then wraps it in the SCD header used by BGM files,
   looping the whole track).
2. Clears any existing `.scd` files from the target `sound/mylist` folder and
   writes the new tracks as `1.scd`, `2.scd`, ...
3. Regenerates the `Options` array in the mod's Penumbra group JSON so each
   track is a selectable option that remaps `sound/dam.scd` to its `.scd` file.

Already-converted tracks are cached (by source file size/mtime) and skipped on
subsequent applies unless the source file changes.

## Prerequisites

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) available on your `PATH`, or point
  the app at a specific `ffmpeg`/`ffmpeg.exe` binary via the "ffmpeg path" field.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Usage

1. **New** a playlist on the left.
2. Set **Group JSON** to the Penumbra option-group JSON file inside your mod
   (e.g. `group_004_music __ my playlist.json`). Use **Auto (sound/mylist)** to
   set the SCD folder to `<mod folder>/sound/mylist` automatically.
3. **Add Files...** to build the track list (drag to reorder — order determines
   which numbered `.scd` slot and Penumbra option each track becomes).
4. **Rename** a track to control the name shown for that option in Penumbra's
   mod configuration UI.
5. Click **Apply Playlist**.

App state (all playlists, track lists, and target paths) is saved automatically
to `~/.thunderdome_playlists.json`.

## Notes

- The SCD header template (`app/resources/OGG.bin`) and conversion algorithm are
  ported from [FFXIVVoicePackCreator](https://github.com/Sebane1/FFXIVVoicePackCreator)'s
  `SCDGenerator.GenerateOGG`.
- The root fields of the group JSON (`Name`, `Description`, `Priority`, etc.) and
  the `Off` option are preserved; only `Options[1:]` are regenerated from the
  playlist's tracks.
# thunderdome-playlist-manager
