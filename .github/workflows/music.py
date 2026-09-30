"""
music.py - picks a background track and mixes it quietly under the voice.
The music automatically gets quieter while the anchor is talking ("ducking"),
fades in at the start and fades out at the end.
Tracks live in the music/ folder. Drop extra .mp3 files in there and they are used too.
"""
import datetime
import glob
import os
import subprocess

import config


def pick_track():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.MUSIC_FOLDER)
    tracks = sorted(glob.glob(os.path.join(folder, "*.mp3")))
    if not tracks:
        return None
    return tracks[datetime.date.today().toordinal() % len(tracks)]  # a different one each day


def mix(video_in, video_out, duration):
    track = pick_track()
    if not track or not config.BACKGROUND_MUSIC:
        return False
    fade_out_start = max(duration - 4, 0)
    vol = config.MUSIC_VOLUME
    intro = config.MUSIC_INTRO_SECONDS
    boost = config.MUSIC_INTRO_BOOST
    filt = (
        "[0:a]asplit=2[voice][sc];"
        f"[1:a]volume={vol},volume='if(lt(t,{intro}),{boost},1)':eval=frame,afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start:.2f}:d=4[m];"
        "[m][sc]sidechaincompress=threshold=0.03:ratio=3:attack=30:release=500[duck];"
        "[voice][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[a]"
    )
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", video_in, "-stream_loop", "-1", "-i", track,
        "-filter_complex", filt,
        "-map", "0:v", "-map", "[a]", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k", "-shortest", video_out])
    print(f"[music] mixed in {os.path.basename(track)}")
    return True
