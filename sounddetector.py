import os
import sys
import threading
import time
from typing import Callable, Optional, List, Dict, Tuple
import numpy as np
import soundcard as sc
from scipy import signal
import scipy.io.wavfile as wavfile

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import winsound
except ImportError:
    winsound = None

try:
    import proctap
except ImportError:
    proctap = None

class AudioDeviceManager:
    @staticmethod
    def get_devices() -> List[Dict[str, any]]:
        devices = []
        try:
            mics = sc.all_microphones(include_loopback=True)
            for m in mics:
                devices.append({
                    "id": m.id,
                    "name": m.name,
                    "is_loopback": m.isloopback,
                    "display": f"[Speaker/Game] {m.name}" if m.isloopback else f"[Mic] {m.name}",
                    "obj": m
                })
        except Exception:
            pass
        return devices

    @staticmethod
    def get_default_loopback() -> Optional[Dict[str, any]]:
        try:
            default_sp = sc.default_speaker()
            mics = sc.all_microphones(include_loopback=True)
            for m in mics:
                if m.isloopback and default_sp.name in m.name:
                    return {
                        "id": m.id,
                        "name": m.name,
                        "is_loopback": True,
                        "display": f"[Game Audio] {m.name}",
                        "obj": m
                    }
            for m in mics:
                if m.isloopback:
                    return {
                        "id": m.id,
                        "name": m.name,
                        "is_loopback": True,
                        "display": f"[Game Audio] {m.name}",
                        "obj": m
                    }
        except Exception:
            pass
        return None

class SoundDetector:
    MATCH_FS = 16000

    def __init__(
        self,
        device_obj=None,
        target_pid: Optional[int] = None,
        samplerate: int = 44100,
        blocksize: int = 2048,
        match_threshold: float = 0.50,
        cooldown: float = 3.0,
        on_level_callback: Optional[Callable[[float, float], None]] = None,
        on_trigger_callback: Optional[Callable[[float], None]] = None,
        on_status_callback: Optional[Callable[[str], None]] = None,
    ):
        self.device_obj = device_obj
        self.target_pid = target_pid
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.match_threshold = match_threshold
        self.cooldown = cooldown

        self.on_level_callback = on_level_callback
        self.on_trigger_callback = on_trigger_callback
        self.on_status_callback = on_status_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cooldown_until = 0.0

        self.template_raw: Optional[np.ndarray] = None
        self.template_norm: Optional[np.ndarray] = None
        self.template_name: str = "No sound loaded"
        self.template_filepath: Optional[str] = None
        self.template_duration: float = 0.0

        self._rolling_buffer = np.zeros(int(self.MATCH_FS * 1.0), dtype=np.float32)

    def update_settings(
        self,
        match_threshold: Optional[float] = None,
        cooldown: Optional[float] = None,
        device_obj=None,
        target_pid: Optional[int] = -1,
    ):
        if match_threshold is not None:
            self.match_threshold = float(match_threshold)
        if cooldown is not None:
            self.cooldown = float(cooldown)

        restart = False
        if device_obj is not None and device_obj != self.device_obj:
            self.device_obj = device_obj
            restart = True

        if target_pid != -1 and target_pid != self.target_pid:
            self.target_pid = target_pid
            restart = True

        if restart and self._running:
            self.stop()
            self.start()

    def load_sound_file(self, filepath: str) -> Tuple[bool, str]:
        if not os.path.exists(filepath):
            return False, "File not found."

        try:
            if sf is not None:
                data, fs = sf.read(filepath, dtype='float32')
            else:
                fs, int_data = wavfile.read(filepath)
                data = int_data.astype(np.float32) / 32768.0

            if data.ndim > 1:
                data = np.mean(data, axis=1)

            peak_val = float(np.max(np.abs(data)))
            if peak_val < 0.008:
                return False, f"Audio signal too quiet (Peak: {peak_val:.4f})."

            if fs != self.MATCH_FS:
                num_target = int(len(data) * self.MATCH_FS / fs)
                data = signal.resample(data, num_target).astype(np.float32)

            energy = np.abs(data)
            thresh = 0.04 * np.max(energy)
            non_silent = np.where(energy > thresh)[0]
            if len(non_silent) > 0:
                data = data[non_silent[0]:non_silent[-1] + 1]

            max_len = int(self.MATCH_FS * 1.2)
            if len(data) > max_len:
                data = data[:max_len]

            if len(data) < int(self.MATCH_FS * 0.04):
                return False, "Audio cue too short (< 0.04s)."

            self.template_raw = data
            self.template_duration = len(data) / self.MATCH_FS
            self.template_name = os.path.basename(filepath)
            self.template_filepath = filepath

            norm_t = data - np.mean(data)
            norm_val = np.linalg.norm(norm_t)
            if norm_val > 1e-5:
                self.template_norm = (norm_t / norm_val).astype(np.float32)
            else:
                self.template_norm = None
                return False, "Insufficient audio signal dynamics."

            buffer_len = max(int(self.MATCH_FS * 1.0), int(len(data) * 2.2))
            self._rolling_buffer = np.zeros(buffer_len, dtype=np.float32)

            return True, f"{self.template_name} ({self.template_duration:.2f}s)"
        except Exception as e:
            return False, f"Load error: {e}"

    def play_template(self):
        if self.template_filepath and os.path.exists(self.template_filepath) and winsound is not None:
            try:
                winsound.PlaySound(self.template_filepath, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except Exception:
                pass

        if self.template_raw is not None:
            try:
                base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
                temp_wav = os.path.join(base_dir, "temp_play.wav")
                wav_int16 = (self.template_raw / (np.max(np.abs(self.template_raw)) + 1e-9) * 32000).astype(np.int16)
                wavfile.write(temp_wav, self.MATCH_FS, wav_int16)
                if winsound is not None:
                    winsound.PlaySound(temp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
                elif sd is not None:
                    sd.play(self.template_raw, samplerate=self.MATCH_FS, blocking=False)
            except Exception:
                pass

    def record_live_smart(
        self,
        timeout: float = 12.0,
        trigger_threshold: float = 0.020,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        if status_callback:
            status_callback("Listening for audio cue (trigger sound now)...")

        if self.target_pid is not None and proctap is not None:
            try:
                cap = proctap.ProcessAudioCapture(pid=self.target_pid)
                cap.start()
                start_time = time.time()
                ring_buffer = []
                pre_buffer_chunks = 16

                while time.time() - start_time < timeout:
                    chunk = cap.read(timeout=0.05)
                    if chunk is None or len(chunk) == 0:
                        continue

                    arr = np.frombuffer(chunk, dtype=np.float32).reshape(-1, 2)
                    mono = np.mean(arr, axis=1)

                    ring_buffer.append(mono)
                    if len(ring_buffer) > pre_buffer_chunks:
                        ring_buffer.pop(0)

                    rms = float(np.sqrt(np.mean(mono ** 2)))
                    if rms >= trigger_threshold:
                        post_frames_needed = int(48000 * 0.35)
                        post_chunks = []
                        post_count = 0
                        while post_count < post_frames_needed and time.time() - start_time < timeout + 2.0:
                            c = cap.read(timeout=0.05)
                            if c is not None and len(c) > 0:
                                a = np.frombuffer(c, dtype=np.float32).reshape(-1, 2)
                                m = np.mean(a, axis=1)
                                post_chunks.append(m)
                                post_count += len(m)

                        full_audio = np.concatenate(ring_buffer + post_chunks)
                        cap.stop()
                        cap.close()

                        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
                        save_path = os.path.join(base_dir, "recorded_sound.wav")
                        full_int16 = (full_audio / (np.max(np.abs(full_audio)) + 1e-9) * 30000).astype(np.int16)
                        wavfile.write(save_path, 48000, full_int16)

                        success, msg = self.load_sound_file(save_path)
                        if success:
                            self.play_template()
                            return True, f"Target app sound captured! ({self.template_duration:.2f}s)"
                        else:
                            return False, msg
                    time.sleep(0.002)

                cap.stop()
                cap.close()
                return False, "Timeout (12s). No sound detected from target window. Try again!"
            except Exception:
                pass

        device = self.device_obj
        if device is None:
            default_dev = AudioDeviceManager.get_default_loopback()
            device = default_dev["obj"] if default_dev else None

        if device is None:
            return False, "No audio device selected."

        chunk_size = 1024
        start_time = time.time()
        ring_buffer = []
        pre_buffer_chunks = 4

        try:
            with device.recorder(samplerate=self.samplerate, blocksize=chunk_size) as rec:
                while time.time() - start_time < timeout:
                    data = rec.record(numframes=chunk_size)
                    if data.ndim > 1:
                        mono = np.mean(data, axis=1)
                    else:
                        mono = data

                    ring_buffer.append(mono)
                    if len(ring_buffer) > pre_buffer_chunks:
                        ring_buffer.pop(0)

                    rms = float(np.sqrt(np.mean(mono ** 2)))
                    if rms >= trigger_threshold:
                        post_frames = int(self.samplerate * 0.35)
                        post_data = rec.record(numframes=post_frames)
                        if post_data.ndim > 1:
                            post_mono = np.mean(post_data, axis=1)
                        else:
                            post_mono = post_data

                        full_audio = np.concatenate(ring_buffer + [post_mono])

                        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
                        save_path = os.path.join(base_dir, "recorded_sound.wav")
                        full_int16 = (full_audio / (np.max(np.abs(full_audio)) + 1e-9) * 30000).astype(np.int16)
                        wavfile.write(save_path, self.samplerate, full_int16)

                        success, msg = self.load_sound_file(save_path)
                        if success:
                            self.play_template()
                            return True, f"Sound captured successfully! ({self.template_duration:.2f}s)"
                        else:
                            return False, msg

                    time.sleep(0.005)

            return False, "Timeout (12s). No sound detected. Try again!"
        except Exception as e:
            return False, f"Recording error: {e}"

    def clear_buffer(self):
        self._rolling_buffer = np.zeros_like(self._rolling_buffer)

    def trigger_external_cooldown(self, duration: float):
        self._cooldown_until = time.time() + duration
        self.clear_buffer()

    @property
    def is_in_cooldown(self) -> bool:
        return time.time() < self._cooldown_until

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if self.on_status_callback:
            self.on_status_callback("LISTENING")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        if self.on_status_callback:
            self.on_status_callback("IDLE")

    def _run_loop(self):
        if self.target_pid is not None and proctap is not None:
            try:
                self._run_loop_proctap(self.target_pid)
                return
            except Exception:
                pass
        self._run_loop_soundcard()

    def _run_loop_proctap(self, pid: int):
        cap = None
        try:
            cap = proctap.ProcessAudioCapture(pid=pid)
            cap.start()

            acc_frames = []
            acc_count = 0
            target_chunk_frames = 1920

            while self._running:
                chunk = cap.read(timeout=0.05)
                if not self._running:
                    break
                if chunk is None or len(chunk) == 0:
                    continue

                arr = np.frombuffer(chunk, dtype=np.float32).reshape(-1, 2)
                mono_chunk = np.mean(arr, axis=1)
                acc_frames.append(mono_chunk)
                acc_count += len(mono_chunk)

                if acc_count >= target_chunk_frames:
                    mono = np.concatenate(acc_frames)
                    acc_frames = []
                    acc_count = 0

                    rms = float(np.sqrt(np.mean(mono ** 2)))

                    target_frames = int(len(mono) * self.MATCH_FS / 48000)
                    mono_ds = signal.resample(mono, target_frames).astype(np.float32)

                    buf_len = len(self._rolling_buffer)
                    n_in = len(mono_ds)
                    if n_in >= buf_len:
                        self._rolling_buffer = mono_ds[-buf_len:]
                    else:
                        self._rolling_buffer = np.roll(self._rolling_buffer, -n_in)
                        self._rolling_buffer[-n_in:] = mono_ds

                    match_score = 0.0
                    if self.template_norm is not None:
                        buf_rms = float(np.sqrt(np.mean(self._rolling_buffer ** 2)))
                        if buf_rms > 0.003:
                            M = len(self.template_norm)
                            X = self._rolling_buffer
                            C = signal.correlate(X, self.template_norm, mode='valid', method='fft')
                            cs_X = np.pad(np.cumsum(X, dtype=np.float64), (1, 0))
                            cs_X2 = np.pad(np.cumsum(X ** 2, dtype=np.float64), (1, 0))
                            sum_X = cs_X[M:] - cs_X[:-M]
                            sum_X2 = cs_X2[M:] - cs_X2[:-M]
                            var_X = np.maximum(sum_X2 - (sum_X ** 2) / M, 0.0)
                            norm_X = np.sqrt(var_X)
                            valid = norm_X > 1e-4
                            ncc = np.zeros_like(C)
                            ncc[valid] = C[valid] / norm_X[valid]
                            match_score = max(0.0, min(1.0, float(np.max(ncc)))) if len(ncc) > 0 else 0.0

                    if self.on_level_callback:
                        self.on_level_callback(rms, match_score)

                    now = time.time()
                    if now < self._cooldown_until:
                        continue

                    if match_score >= self.match_threshold:
                        self._cooldown_until = now + self.cooldown
                        self.clear_buffer()
                        if self.on_trigger_callback:
                            self.on_trigger_callback(match_score)

        except Exception:
            if self._running and self.on_status_callback:
                self.on_status_callback("ERROR")
        finally:
            if cap is not None:
                try:
                    cap.stop()
                    cap.close()
                except Exception:
                    pass
            self._running = False

    def _run_loop_soundcard(self):
        device = self.device_obj
        if device is None:
            default_dev = AudioDeviceManager.get_default_loopback()
            device = default_dev["obj"] if default_dev else None
            if device is None:
                mics = sc.all_microphones(include_loopback=True)
                if mics:
                    device = mics[0]

        if device is None:
            self._running = False
            if self.on_status_callback:
                self.on_status_callback("ERROR_NO_DEVICE")
            return

        try:
            with device.recorder(samplerate=self.samplerate, blocksize=self.blocksize) as rec:
                while self._running:
                    data = rec.record(numframes=self.blocksize)
                    if data is None or len(data) == 0:
                        time.sleep(0.01)
                        continue

                    if data.ndim > 1:
                        mono = np.mean(data, axis=1)
                    else:
                        mono = data

                    rms = float(np.sqrt(np.mean(mono ** 2)))

                    target_frames = int(len(mono) * self.MATCH_FS / self.samplerate)
                    mono_ds = signal.resample(mono, target_frames).astype(np.float32)

                    buf_len = len(self._rolling_buffer)
                    n_in = len(mono_ds)
                    if n_in >= buf_len:
                        self._rolling_buffer = mono_ds[-buf_len:]
                    else:
                        self._rolling_buffer = np.roll(self._rolling_buffer, -n_in)
                        self._rolling_buffer[-n_in:] = mono_ds

                    match_score = 0.0
                    if self.template_norm is not None:
                        buf_rms = float(np.sqrt(np.mean(self._rolling_buffer ** 2)))
                        if buf_rms > 0.003:
                            M = len(self.template_norm)
                            X = self._rolling_buffer
                            C = signal.correlate(X, self.template_norm, mode='valid', method='fft')
                            cs_X = np.pad(np.cumsum(X, dtype=np.float64), (1, 0))
                            cs_X2 = np.pad(np.cumsum(X ** 2, dtype=np.float64), (1, 0))
                            sum_X = cs_X[M:] - cs_X[:-M]
                            sum_X2 = cs_X2[M:] - cs_X2[:-M]
                            var_X = np.maximum(sum_X2 - (sum_X ** 2) / M, 0.0)
                            norm_X = np.sqrt(var_X)
                            valid = norm_X > 1e-4
                            ncc = np.zeros_like(C)
                            ncc[valid] = C[valid] / norm_X[valid]
                            match_score = max(0.0, min(1.0, float(np.max(ncc)))) if len(ncc) > 0 else 0.0

                    if self.on_level_callback:
                        self.on_level_callback(rms, match_score)

                    now = time.time()
                    if now < self._cooldown_until:
                        continue

                    if match_score >= self.match_threshold:
                        self._cooldown_until = now + self.cooldown
                        self.clear_buffer()
                        if self.on_trigger_callback:
                            self.on_trigger_callback(match_score)

        except Exception:
            if self._running and self.on_status_callback:
                self.on_status_callback("ERROR")
        finally:
            self._running = False
