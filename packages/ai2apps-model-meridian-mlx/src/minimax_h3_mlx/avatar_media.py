"""Runtime-bundled PyAV encoding; no external ffmpeg executable is required."""
from fractions import Fraction
from pathlib import Path
import av
import numpy as np
import soundfile as sf


def save_segment(path, frames, fps=24):
    with av.open(str(path), 'w', format='mp4') as output:
        stream = output.add_stream('libx264', rate=fps)
        stream.width, stream.height = frames.shape[2], frames.shape[1]
        stream.pix_fmt = 'yuv420p'
        stream.options = {'crf': '18', 'preset': 'medium', 'bf': '0'}
        for index, pixels in enumerate(frames):
            frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(pixels), format='rgb24')
            frame.pts, frame.time_base = index, Fraction(1, fps)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)


def join_segments(paths, audio_path, destination, *, fps=24, cancelled=None):
    """Copy H.264 packets with absolute timestamps, encode original PCM only once."""
    def check():
        if cancelled and cancelled():
            raise InterruptedError('Avatar mux cancelled')
    check()
    samples, sample_rate = sf.read(str(audio_path), dtype='float32', always_2d=True)
    layout = 'mono' if samples.shape[1] == 1 else 'stereo'
    destination = Path(destination)
    temporary = destination.with_name(destination.stem + '.partial.mp4')
    try:
        with av.open(str(paths[0])) as first, av.open(str(temporary), 'w', format='mp4', options={'movflags': '+faststart'}) as output:
            source_stream = first.streams.video[0]
            video = output.add_stream_from_template(source_stream)
            audio = output.add_stream('aac', rate=sample_rate)
            audio.layout = layout
            audio.bit_rate = 192000
            frame_offset = 0
            for path in paths:
                check()
                with av.open(str(path)) as segment:
                    source = segment.streams.video[0]
                    if (source.width, source.height, source.codec_context.extradata) != (source_stream.width, source_stream.height, source_stream.codec_context.extradata):
                        raise ValueError('Segment codec parameters differ')
                    count = 0
                    for packet in segment.demux(source):
                        if packet.dts is None:
                            continue
                        check()
                        if packet.pts != packet.dts or packet.pts * packet.time_base != Fraction(count, fps):
                            raise ValueError('Segment requires contiguous zero-origin frames without B frames')
                        offset = Fraction(frame_offset, fps) / packet.time_base
                        if offset.denominator != 1:
                            raise ValueError('Non-integral segment timestamp offset')
                        packet.pts += int(offset)
                        packet.dts += int(offset)
                        packet.stream = video
                        output.mux(packet)
                        count += 1
                    if not count:
                        raise ValueError('Empty segment')
                    frame_offset += count
            for offset in range(0, len(samples), 1024):
                check()
                pcm = np.ascontiguousarray(samples[offset:offset+1024].T)
                frame = av.AudioFrame.from_ndarray(pcm, format='fltp', layout=layout)
                frame.sample_rate = sample_rate
                frame.pts, frame.time_base = offset, Fraction(1, sample_rate)
                for packet in audio.encode(frame):
                    output.mux(packet)
            for packet in audio.encode():
                output.mux(packet)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
