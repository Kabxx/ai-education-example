import asyncio
import queue
import threading

from pydub import AudioSegment
from pydub.playback import play


class NonBlockingAudioQueuePlayer:
    def __init__(self):
        self._queue = queue.Queue()
        self._th = threading.Thread(target=self._worker)

    def __enter__(self):
        """当进入 with 块时初始化和启动播放线程"""
        self._th.start()
        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):
        """当退出 with 块时，清理资源和停止播放线程"""
        self._queue.put(None)  # 向队列发送 None 以停止播放线程
        self._th.join()

    def _worker(self):
        """从队列中获取音频并播放"""
        while True:
            audio = self._queue.get()
            self._queue.task_done()

            if audio is None:  # 如果队列中是 None，表示退出播放线程
                break

            try:
                play(audio)  # 播放音频
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"Error playing audio: {e}")

        print("Audio playback thread stopped.")

    def play(
        self,
        audio: AudioSegment,
    ):
        self._queue.put(audio)


def async_play_audio(audio: AudioSegment):
    """异步播放音频"""
    asyncio.to_thread(play, (audio,))
