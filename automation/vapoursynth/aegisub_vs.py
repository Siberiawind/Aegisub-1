"""
Utility functions for loading video files into Aegisub using the Vapoursynth
video provider.

When encountering a file whose file extension is not .py or .vpy, the
Vapoursynth audio and video providers will execute the respective default
script set in Aegisub's configuration, with the following string variables set:
- filename: The path to the file that's being opened.
- __aegi_data, __aegi_dictionary, __aegi_local, __aegi_script, __aegi_temp, __aegi_user:
  The values of ?data, ?dictionary, etc. respectively.
- __aegi_vscache: The path to a directory where the Vapoursynth script can
  store cache files. This directory is cleaned by Aegisub when it gets too
  large (as defined by Aegisub's configuration).

The provider reads the video from the script's 0-th output node. By default,
the video is assumed to be CFR. The script can pass further information to
Aegisub using the following variables:
    - __aegi_timecodes: List[int] | str: The timecodes for the video, or the
      path to a timecodes file.
    - __aegi_keyframes: List[int] | str: List of frame numbers to load as
      keyframes, or the path to a keyframes file.
    - __aegi_hasaudio: int: If nonzero, Aegisub will try to load an audio track
      from the same file.

This module provides some utility functions to obtain timecodes, keyframes, and
other data.
"""
import os
import os.path
import re
from collections import deque
from typing import Any, Dict, List, Tuple

import vapoursynth as vs
core = vs.core

def make_lwi_cache_filename(filename: str) -> str:
    """
    Given a path to a video, will return a file name like the one LWLibavSource
    would use for a .lwi file.
    """
    max_len = 254
    extension = ".lwi"

    if len(filename) + len(extension) > max_len:
        filename = filename[-(max_len + len(extension)):]

    return "".join(("_" if c in "/\\:" else c) for c in filename) + extension


def make_keyframes_filename(filename: str) -> str:
    """
    Given a path `path/to/file.mkv`, will return the path
    `path/to/file keyframes.txt`.
    """
    extlen = filename[::-1].find(".") + 1
    return filename[:len(filename) - extlen] + " keyframes.txt"


lwindex_re1 = re.compile(r"Index=(?P<Index>-?[0-9]+),POS=(?P<POS>-?[0-9]+),PTS=(?P<PTS>-?[0-9]+),DTS=(?P<DTS>-?[0-9]+),EDI=(?P<EDI>-?[0-9]+)")
lwindex_re2 = re.compile(r"Key=(?P<Key>-?[0-9]+),Pic=(?P<Pic>-?[0-9]+),POC=(?P<POC>-?[0-9]+),Repeat=(?P<Repeat>-?[0-9]+),Field=(?P<Field>-?[0-9]+)")
streaminfo_re = re.compile(r"Codec=(?P<Codec>[0-9]+),TimeBase=(?P<TimeBase>[0-9\/]+),Width=(?P<Width>[0-9]+),Height=(?P<Height>[0-9]+),Format=(?P<Format>[0-9a-zA-Z]+),ColorSpace=(?P<ColorSpace>[0-9]+)")

class LWIndexFrame:
    pts: int
    key: int

    def __init__(self, raw: list[str]):
        match1 = lwindex_re1.match(raw[0])
        match2 = lwindex_re2.match(raw[1])
        if not match1 or not match2:
            raise ValueError("Invalid lwindex format")
        self.pts = int(match1.group("PTS"))
        self.key = int(match2.group("Key"))

    def __int__(self) -> int:
        return self.pts


def info_from_lwindex(indexfile: str) -> Dict[str, List[int]]:
    """
    Given a path to an .lwi file, will return a dictionary containing
    information about the video, with the keys
    - timcodes: The timecodes.
    - keyframes: Array of frame numbers of keyframes.
    """
    with open(indexfile, encoding="latin1") as f:
        index = f.read().splitlines()

    indexstart, indexend = index.index("</StreamInfo>") + 1, index.index("</LibavReaderIndex>")
    frames = [LWIndexFrame(index[i:i+2]) for i in range(indexstart, indexend, 2)]
    frames.sort(key=int)

    streaminfo = streaminfo_re.match(index[indexstart - 2])
    if not streaminfo:
        raise ValueError("Invalid lwindex format")

    timebase_num, timebase_den = [int(i) for i in streaminfo.group("TimeBase").split("/")]

    return {
        "timecodes": [(f.pts * 1000 * timebase_num) // timebase_den for f in frames],
        "keyframes": [i for i, f in enumerate(frames) if f.key],
    }


def wrap_lwlibavsource(filename: str, cachedir: str, **kwargs: Any) -> Tuple[vs.VideoNode, Dict[str, List[int]]]:
    """
    Given a path to a video file and a directory to store index files in
    (usually __aegi_vscache), will open the video with LWLibavSource and read
    the generated .lwi file to obtain the timecodes and keyframes.
    Additional keyword arguments are passed on to LWLibavSource.
    """
    try:
        os.mkdir(cachedir)
    except FileExistsError:
        pass
    cachefile = os.path.join(cachedir, make_lwi_cache_filename(filename))

    if not hasattr(core, "lsmas"):
        raise vs.Error("To use Aegisub's LWLibavSource wrapper, the `lsmas` plugin for VapourSynth must be installed")

    if b"-Dcachedir" not in core.lsmas.Version()["config"]:
        raise vs.Error("To use Aegisub's LWLibavSource wrapper, the `lsmas` plugin must support the `cachedir` option for LWLibavSource.")

    clip = core.lsmas.LWLibavSource(source=filename, cachefile=cachefile, **kwargs)

    return clip, info_from_lwindex(cachefile)


def make_keyframes(clip: vs.VideoNode, use_scxvid: bool = False,
                   resize_h: int = 360, resize_format: int = vs.YUV420P8,
                   **kwargs: Any) -> List[int]:
    """
    Generates a list of keyframes from a clip, using either WWXD or Scxvid.
    Will be slightly more efficient with the `akarin` plugin installed.

    :param clip:             Clip to process.
    :param use_scxvid:       Whether to use Scxvid. If False, the function uses WWXD.
    :param resize_h:         Height to resize the clip to before processing.
    :param resize_format:    Format to convert the clip to before processing.

    The remaining keyword arguments are passed on to the respective filter.
    """

    clip = core.resize.Bilinear(clip, width=resize_h * clip.width // clip.height, height=resize_h, format=resize_format);
    try:
        clip = core.scxvid.Scxvid(clip, **kwargs) if use_scxvid else core.wwxd.WWXD(clip, **kwargs)
    except AttributeError:
        raise vs.Error("To use the keyframe generation, the `{}` plugin for VapourSynth must be installed"
                       .format("scxvid" if use_scxvid else "wwxd"))

    keyframes = {}
    def _cb(n: int, f: vs.VideoFrame) -> vs.VideoFrame:
        keyframes[n] = f.props._SceneChangePrev if use_scxvid else f.props.Scenechange # type: ignore
        return f

    deque(clip.std.ModifyFrame(clip, _cb).frames(close=True), 0)
    return [n for n in range(clip.num_frames) if keyframes[n]]


def save_keyframes(filename: str, keyframes: List[int]):
    """
    Saves a list of keyframes in Aegisub's keyframe format v1 to a file with
    the given filename.
    """
    with open(filename, "w") as f:
        f.write("# keyframe format v1\n")
        f.write("fps 0\n")
        f.write("".join(f"{n}\n" for n in keyframes))


def get_keyframes(filename: str, clip: vs.VideoNode, **kwargs: Any) -> str:
    """
    When not already present, creates a keyframe file for the given clip next
    to the given filename using WWXD or Scxvid (see the make_keyframes docstring).
    Additional keyword arguments are passed on to make_keyframes.
    """
    kffilename = make_keyframes_filename(filename)

    if not os.path.exists(kffilename):
        keyframes = make_keyframes(clip, **kwargs)
        save_keyframes(kffilename, keyframes)

    return kffilename


def check_audio(filename: str, **kwargs: Any) -> bool:
    """
    Checks whether the given file has an audio track by trying to open it with
    BestAudioSource. Requires the `bas` plugin to return correct results, but
    won't crash if it's not installed.
    Additional keyword arguments are passed on to BestAudioSource.
    """
    try:
        vs.core.bas.Source(source=filename, **kwargs)
        return True
    except AttributeError:
        pass
    except vs.Error:
        pass
    return False
