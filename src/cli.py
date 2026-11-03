"""
CLI utility for audio conversion: WAV to MP3 transcoder.

Accepts an input audio file or configuration and outputs conversion results
and compression metrics in JSON format to standard output.
"""

import json
import math
import os
import sys
import wave
from src.constants import (
    ARG_FILE_INDEX,
    ARG_MIN_COUNT,
    AUDIO_DEFAULT_SAMPLE_RATE,
    AUDIO_MAX_CHANNELS,
    AUDIO_MAX_SAMPLE_RATE,
    AUDIO_MIN_CHANNELS,
    AUDIO_MIN_SAMPLE_RATE,
    BITS_PER_KILOBIT,
    BYTES_PER_SAMPLE_16BIT,
    DEFAULT_DURATION_FLOAT,
    EXIT_FAILURE,
    EXIT_SUCCESS,
    FOUR_VAL,
    MAX_DURATION_SEC,
    MIN_DURATION_SEC,
    MP3_DEFAULT_BITRATE_KBPS,
    MP3_FRAME_SCALE_CONSTANT,
    MP3_MAX_BITRATE_KBPS,
    MP3_MIN_BITRATE_KBPS,
    MP3_SAMPLES_PER_FRAME,
    ONE_VAL,
    ROUND_DIGITS,
    THREE_VAL,
    TWO_VAL,
    WAV_RIFF_HEADER_SIZE,
    ZERO_VAL,
)


def _parse_text_payload(text: str) -> dict:
    """Extract raw audio parameters from text payload."""
    cleaned = text.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return json.loads(cleaned)
    result: dict = {}
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line:
            parts = line.split(":", ONE_VAL)
            key = parts[ZERO_VAL].strip().lower()
            val = parts[ONE_VAL].strip()
            result[key] = val
        else:
            tokens = line.split()
            if len(tokens) >= FOUR_VAL:
                result["sample_rate"] = tokens[ZERO_VAL]
                result["channels"] = tokens[ONE_VAL]
                result["bitrate_kbps"] = tokens[TWO_VAL]
                result["duration_sec"] = tokens[THREE_VAL]
    return result


def _validate_audio_params(data: dict) -> dict:
    """Validate and normalize audio parameter values."""
    s_rate = int(data.get("sample_rate", AUDIO_DEFAULT_SAMPLE_RATE))
    chan = int(data.get("channels", AUDIO_MIN_CHANNELS))
    b_rate = int(data.get("bitrate_kbps", MP3_DEFAULT_BITRATE_KBPS))
    dur = float(data.get("duration_sec", DEFAULT_DURATION_FLOAT))

    if s_rate < AUDIO_MIN_SAMPLE_RATE or s_rate > AUDIO_MAX_SAMPLE_RATE:
        raise ValueError(f"Sample rate {s_rate} is out of boundary")
    if chan < AUDIO_MIN_CHANNELS or chan > AUDIO_MAX_CHANNELS:
        raise ValueError(f"Channels count {chan} is out of boundary")
    if b_rate < MP3_MIN_BITRATE_KBPS or b_rate > MP3_MAX_BITRATE_KBPS:
        raise ValueError(f"Bitrate {b_rate} is out of boundary")
    if dur < MIN_DURATION_SEC or dur > MAX_DURATION_SEC:
        raise ValueError(f"Duration {dur} is out of boundary")

    return {
        "sample_rate": s_rate,
        "channels": chan,
        "bitrate_kbps": b_rate,
        "duration_sec": dur,
    }


def _read_wav_binary(file_path: str) -> dict:
    """Extract audio stream parameters from binary WAV header."""
    with wave.open(file_path, "rb") as wav_file:
        s_rate = wav_file.getframerate()
        frames = wav_file.getnframes()
        dur = float(frames) / float(s_rate)
        return {
            "sample_rate": s_rate,
            "channels": wav_file.getnchannels(),
            "bitrate_kbps": MP3_DEFAULT_BITRATE_KBPS,
            "duration_sec": dur,
        }


def parse_audio_input(source: str) -> dict:
    """Read and validate audio configuration from file or text string."""
    if os.path.isfile(source):
        with open(source, "rb") as raw_file:
            lead = raw_file.read(FOUR_VAL)
        if lead == b"RIFF":
            return _validate_audio_params(_read_wav_binary(source))
        with open(source, "r", encoding="utf-8") as text_file:
            content = text_file.read()
    else:
        content = source

    raw_data = _parse_text_payload(content)
    if not raw_data:
        raise ValueError("Empty or invalid audio input payload")
    return _validate_audio_params(raw_data)


def convert_wav_to_mp3(params: dict) -> dict:
    """Perform audio conversion calculation from WAV to MP3 format."""
    s_rate = params["sample_rate"]
    chan = params["channels"]
    b_rate = params["bitrate_kbps"]
    dur = params["duration_sec"]

    total_samples = int(s_rate * dur * chan)
    wav_bytes = int(s_rate * dur * chan * BYTES_PER_SAMPLE_16BIT)
    wav_size = WAV_RIFF_HEADER_SIZE + wav_bytes

    chan_samples = int(s_rate * dur)
    mp3_frames = math.ceil(chan_samples / MP3_SAMPLES_PER_FRAME)
    scale_factor = MP3_FRAME_SCALE_CONSTANT * b_rate * BITS_PER_KILOBIT
    frame_bytes = scale_factor // s_rate
    mp3_size = mp3_frames * frame_bytes

    ratio = round(wav_size / mp3_size, ROUND_DIGITS)
    mode = "MONO" if chan == ONE_VAL else "STEREO"

    return {
        "status": "SUCCESS",
        "source_format": "WAV",
        "target_format": "MP3",
        "sample_rate_hz": s_rate,
        "channels": chan,
        "channel_mode": mode,
        "bitrate_kbps": b_rate,
        "duration_seconds": dur,
        "total_samples": total_samples,
        "wav_size_bytes": wav_size,
        "mp3_frames_count": mp3_frames,
        "mp3_size_bytes": mp3_size,
        "compression_ratio": ratio,
    }


def run_cli(args: list[str]) -> int:
    """Execute audio converter CLI utility with command line arguments."""
    if len(args) < ARG_MIN_COUNT:
        sys.stderr.write("Usage: python -m src.cli <input_audio_file>\n")
        return EXIT_FAILURE

    file_path = args[ARG_FILE_INDEX]
    try:
        params = parse_audio_input(file_path)
        metrics = convert_wav_to_mp3(params)
        sys.stdout.write(json.dumps(metrics, ensure_ascii=False) + "\n")
        return EXIT_SUCCESS
    except Exception as error:
        err_payload = {"status": "ERROR", "error": str(error)}
        sys.stdout.write(json.dumps(err_payload, ensure_ascii=False) + "\n")
        return EXIT_FAILURE


def main() -> None:
    """Entrypoint for console script invocation."""
    sys.exit(run_cli(sys.argv))


if __name__ == "__main__":
    main()
