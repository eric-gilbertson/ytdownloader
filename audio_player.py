import threading, time, pyaudio
from enum import Enum
from pydub import AudioSegment
from djutils import logit

class PlayerState(Enum):
    STOPPED = 1
    PAUSED = 2
    PLAYING = 3

class UpdaterThread(threading.Thread):
    def __init__(self, root):
        super(UpdaterThread, self).__init__()
        self.root = root
        self.remaining = 0
        self.stop_event = threading.Event()
        self.start_event = threading.Event()

    def start_countdown(self, time_seconds):
        self.remaining = time_seconds
        self.stop_event.clear()
        self.start_event.set()

    def run(self):
        while True:
            self.start_event.wait()
            while self.remaining > 1 and not self.stop_event.is_set():
                self.remaining = self.remaining - 1
                m = int(self.remaining // 60)
                s = int(self.remaining % 60)
                self.root.set_countdown(f"{m:02}:{s:02}")
                time.sleep(1)

            self.root.set_title("")
            self.start_event.clear()

            
class PlayerThread(threading.Thread):
    def __init__(self, parent):
        super(PlayerThread, self).__init__()
        self.parent = parent
        self.track_index = -1
        self.state = PlayerState.STOPPED
        self.start_playback = threading.Event()
        self.py_audio = pyaudio.PyAudio()
        self.updater = UpdaterThread(self.parent)
        self.updater.start()

    def is_playing(self):
        return self.state == PlayerState.PLAYING

    def is_stopped(self):
        return self.state == PlayerState.STOPPED

    def stop_player(self):
        self.state = PlayerState.STOPPED

    def play_index(self, index):
        if self.state == PlayerState.PLAYING:
            self.state = PlayerState.STOPPED
            time.sleep(1)
            
        self.track_index = index
        self.start_playback.set()


    def run(self):
        while True:
            self.start_playback.wait()
            self.play_audio()

    def play_audio(self):
        self.start_playback.clear()
        self.state = PlayerState.PLAYING

        while self.is_playing() and (track := self.parent.prepare_track_for_playback(self.track_index)) is not None:
            try:
                self.track_index = self.track_index + 1
                if track.is_stop_file():
                    break

                audio_segment = AudioSegment.from_file(track.file_path)
                kwargs = dict(
                    format=self.py_audio.get_format_from_width(audio_segment.sample_width),
                    channels=audio_segment.channels, rate=audio_segment.frame_rate,
                    frames_per_buffer=4096, output=True,
                )
                dev_index = self.parent._get_selected_device_index()
                if dev_index is not None:
                    kwargs["output_device_index"] = dev_index

                stream = self.py_audio.open(**kwargs)
                chunk_ms = 50  # smooth, low-latency
                pos = 0
                total = len(audio_segment)
                self.updater.start_countdown(total/1000)

                while pos < total and self.is_playing():
                    nxt = min(pos + chunk_ms, total)
                    chunk = audio_segment[pos:nxt]
                    stream.write(chunk.raw_data)
                    pos = nxt

                stream.stop_stream()
                stream.close()
                self.updater.stop_event.set()
            except Exception as ex:
                logit(f"Playback error: {ex}")

        self.state = PlayerState.STOPPED




