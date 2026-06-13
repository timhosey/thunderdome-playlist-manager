import os
import struct
import subprocess
import tempfile

_RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")
_OGG_TEMPLATE_PATH = os.path.join(_RESOURCES_DIR, "OGG.bin")

# Offsets into the OGG.bin SCD header template that must be patched per-track.
_OFF_TOTAL_LENGTH = 0x10   # int32: header length + ogg data length
_OFF_VOLUME = 0xA8         # float32: playback volume
_OFF_DATA_SIZE = 0x1B0     # int32: ogg data length - 0x10
_OFF_CHANNELS = 0x1B4      # int32: channel count
_OFF_SAMPLE_RATE = 0x1B8   # int32: sample rate
_OFF_LOOP_START = 0x1C0    # int32: loop start (bytes)
_OFF_LOOP_END = 0x1C4      # int32: loop end (bytes)

SAMPLE_RATE = 44100
CHANNELS = 2


class ConversionError(Exception):
    pass


def _load_template() -> bytearray:
    with open(_OGG_TEMPLATE_PATH, "rb") as f:
        return bytearray(f.read())


def convert_to_ogg(src_path: str, ffmpeg_path: str = "ffmpeg") -> bytes:
    """Convert an MP3/OGG/etc. source file to normalized 44.1kHz stereo Vorbis OGG bytes."""
    if not os.path.exists(src_path):
        raise ConversionError(f"Source file not found: {src_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_ogg = os.path.join(tmp_dir, "out.ogg")
        base_cmd = [
            ffmpeg_path,
            "-y",
            "-i", src_path,
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
        ]
        # Prefer libvorbis (better quality) but fall back to ffmpeg's built-in
        # native vorbis encoder if libvorbis isn't available in this build.
        for codec_args in (["-c:a", "libvorbis"], ["-c:a", "vorbis", "-strict", "-2"]):
            cmd = base_cmd + codec_args + [tmp_ogg]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                break
        else:
            raise ConversionError(
                f"ffmpeg failed for {src_path}:\n{result.stderr}"
            )
        with open(tmp_ogg, "rb") as f:
            return f.read()


def ogg_to_scd(ogg_bytes: bytes) -> bytes:
    """Wrap normalized OGG bytes in an FFXIV SCD header (loops the whole track)."""
    header = _load_template()
    ogg_size = len(ogg_bytes)
    total_length = len(header) + ogg_size

    struct.pack_into("<i", header, _OFF_TOTAL_LENGTH, total_length)
    struct.pack_into("<f", header, _OFF_VOLUME, 1.0)
    struct.pack_into("<i", header, _OFF_DATA_SIZE, ogg_size - 0x10)
    struct.pack_into("<i", header, _OFF_CHANNELS, CHANNELS)
    struct.pack_into("<i", header, _OFF_SAMPLE_RATE, SAMPLE_RATE)
    struct.pack_into("<i", header, _OFF_LOOP_START, 0)
    struct.pack_into("<i", header, _OFF_LOOP_END, ogg_size)

    return bytes(header) + ogg_bytes


def convert_track(src_path: str, ffmpeg_path: str = "ffmpeg") -> bytes:
    """Convert a source audio file directly to SCD bytes."""
    ogg_bytes = convert_to_ogg(src_path, ffmpeg_path)
    return ogg_to_scd(ogg_bytes)
