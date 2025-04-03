import asyncio
import os
import argparse

from dotenv import find_dotenv, load_dotenv
from aiedu.tts.edge_tts import EdgeTTS
from aiedu.utils.ssml import ssml_to_raw_texts
from aiedu.llm import llm_ssml_answer, llm_ssml_lectures_from_pptx, llm_ssml_conclusion
from aiedu.utils.file import pickle_dump, pickle_load
from aiedu.emotext import emotion
from aiedu.utils.audio import NonBlockingAudioQueuePlayer
from aiedu.utils.websocket import WebSocketServer, websocket_send
from rich import print

_ = load_dotenv(find_dotenv())


async def demo_remote(
    pptx_path: str,
    cache_path: str,
    allow_questions: bool = False,
):

    async def handler(
        websocket,
    ):
        print("websocket connection opened")

        if not os.path.exists(cache_path):
            ssml_lectures, messages_lecture = llm_ssml_lectures_from_pptx(
                pptx_path=pptx_path,
            )
            ssml_conclusion, messages_conclusion = llm_ssml_conclusion(
                messages=messages_lecture,
            )
            ssml_lectures, ssml_conclusion = pickle_dump(
                data=(ssml_lectures, ssml_conclusion),
                path=cache_path,
            )
        else:
            ssml_lectures, ssml_conclusion = pickle_load(
                path=cache_path,
            )

        text_lectures_questions = [[], ["什么是快速开发？"], []]

        tts = EdgeTTS()

        for ssml_lecture, text_lecture_questions in zip(ssml_lectures, text_lectures_questions):

            # 课件主体内容
            text_lecture = "\n".join(ssml_to_raw_texts(ssml_lecture))

            print(f"lecture: \n{text_lecture}\n")
            print(f"emotion: \n{str(emotion(text_lecture))}\n")

            audio_lecture = await tts.audio(ssml_lecture)

            # 发送音频
            await websocket_send(
                websocket,
                header={
                    "type": "audio",
                },
                data=audio_lecture.export(format="mp3").read(),
            )
            await websocket.recv()

            # 问题中断
            if allow_questions:

                for text_question in text_lecture_questions:
                    # 问题内容
                    ssml_answer, _ = llm_ssml_answer(
                        contexts=text_lecture,
                        question=text_question,
                    )

                    text_answer = "\n".join(ssml_to_raw_texts(ssml_answer))

                    print(f"question: {text_question}\n")
                    print(f"answer: {text_answer}\n")
                    print(f"emotion: {str(emotion(text_answer))}\n")

                    audio_answer = await tts.audio(ssml_answer)

                    # 发送音频
                    await websocket_send(
                        websocket,
                        header={
                            "type": "audio",
                        },
                        data=audio_answer.export(format="mp3").read(),
                    )
                    await websocket.recv()

        # 课件总结
        text_conclusion = "\n".join(ssml_to_raw_texts(ssml_conclusion))

        print(f"conclusion: \n{text_conclusion}\n")
        print(f"emotion: \n{str(emotion(text_conclusion))}\n")

        audio_conclusion = await tts.audio(ssml_conclusion)

        await websocket_send(
            websocket,
            header={
                "type": "audio",
            },
            data=audio_conclusion.export(format="mp3").read(),
        )
        await websocket.recv()

    # 启动WebSocket服务器
    await WebSocketServer(
        handler=handler,
        host="localhost",
        port=8080,
    ).serve()


async def demo_local(
    pptx_path: str,
    cache_path: str,
    allow_questions: bool = False,
):
    with NonBlockingAudioQueuePlayer() as player:

        if not os.path.exists(cache_path):
            ssml_lectures, messages_lecture = llm_ssml_lectures_from_pptx(
                pptx_path=pptx_path,
            )
            ssml_conclusion, messages_conclusion = llm_ssml_conclusion(
                messages=messages_lecture,
            )
            ssml_lectures, ssml_conclusion = pickle_dump(
                data=(ssml_lectures, ssml_conclusion),
                path=cache_path,
            )
        else:
            ssml_lectures, ssml_conclusion = pickle_load(
                path=cache_path,
            )

        text_lectures_questions = [[], ["什么是快速开发？"], []]

        tts = EdgeTTS()

        for ssml_lecture, text_lecture_questions in zip(ssml_lectures, text_lectures_questions):
            # 课件主体内容
            text_lecture = "\n".join(ssml_to_raw_texts(ssml_lecture))

            print(f"lecture: \n{text_lecture}\n")
            print(f"emotion: \n{str(emotion(text_lecture))}\n")

            # 播放音频
            audio_lecture = await tts.audio(ssml_lecture)
            player.play(audio_lecture)

            # 问题中断
            if allow_questions:

                for text_question in text_lecture_questions:

                    ssml_answer, _ = llm_ssml_answer(
                        contexts=text_lecture,
                        question=text_question,
                    )

                    text_answer = "\n".join(ssml_to_raw_texts(ssml_answer))

                    # 打印问题和答案
                    print(f"question: {text_question}\n")
                    print(f"answer: {text_answer}\n")
                    print(f"emotion: {str(emotion(text_answer))}\n")

                    # 播放音频
                    audio_answer = await tts.audio(ssml_answer)
                    player.play(audio_answer)

        # 课件总结
        text_conclusion = "\n".join(ssml_to_raw_texts(ssml_conclusion))

        print(f"conclusion: \n{text_conclusion}\n")
        print(f"emotion: \n{str(emotion(text_conclusion))}\n")

        audio_conclusion = await tts.audio(ssml_conclusion)
        player.play(audio_conclusion)


async def main(
    pptx_path: str,
    cache_path: str,
):
    await demo_local(
        pptx_path=pptx_path,
        cache_path=cache_path,
        allow_questions=True,
    )
    # await demo_remote(
    #     pptx_path=pptx_path,
    #     cache_path=cache_path,
    #     allow_questions=True,
    # )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Education",
    )
    parser.add_argument(
        "--pptx_path",
        type=str,
        help="Path to the PPTX file.",
    )
    parser.add_argument(
        "--cache_path",
        type=str,
        help="Path to the cache pickle file.",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            pptx_path=args.pptx_path,
            cache_path=args.cache_path,
        )
    )
