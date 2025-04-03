import io
from aiedu.tts.base import BaseTTS
from aiedu.utils.decorator import async_retry
from aiedu.utils.ssml import ssml_to_raw_texts

from pydub import AudioSegment

import edge_tts


class EdgeTTS(BaseTTS):
    def __init__(
        self,
        voice: str = "zh-CN-XiaoyiNeural",
    ):
        super().__init__()
        self.voice = voice

    @async_retry(max_retry=10)
    async def audio(
        self,
        ssml: str,
    ) -> AudioSegment:
        """将SSML文本转换为原始文本并生成音频"""
        # 将 SSML 文本转换为原始文本
        text = "\n".join(ssml_to_raw_texts(ssml))
        # 创建 Communicate 对象
        communicate = edge_tts.Communicate(text=text, voice=self.voice)
        # 通过流式获取音频数据并存储
        audio = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        return AudioSegment.from_file(io.BytesIO(audio), format="mp3")
