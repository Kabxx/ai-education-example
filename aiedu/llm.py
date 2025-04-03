import re
from typing import Dict, List, Tuple, Union

import aisuite

from aiedu.utils.decorator import retry
from aiedu.utils.pptx import pptx_content_generator
from aiedu.resources.prompts import PROMPT_PPTX_TO_SSMLS, PROMPT_QUESTION_TO_SSMLS


class LLMMessage:
    def __init__(
        self,
        role: str,
    ):
        self.role = role
        self.contents: List[Dict] = []

    def text(
        self,
        text: str,
    ):
        self.contents.append(
            {
                "type": "text",
                "text": text,
            }
        )
        return self

    def image(
        self,
        base64_image_url: str,
    ):
        self.contents.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": base64_image_url,
                },
            }
        )
        return self

    def unwrap(self) -> Dict:
        return {
            "role": self.role,
            "content": self.contents,
        }


@retry(max_retry=3)
def llm_response(
    client: aisuite.Client,
    messages: List[Dict[str, str]],
    model: str = "openai:gpt-4o",
    temperature: float = 0.5,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


@retry(max_retry=2)
def llm_ssml(
    client: aisuite.Client,
    messages: List[Dict[str, str]],
) -> str:
    return re.search(r"```ssml([\s\S]+)```", llm_response(client=client, messages=messages), re.DOTALL).group(1)


def llm_ssml_lectures_from_pptx(
    pptx_path: str,
) -> Tuple[List[str], List[Dict]]:
    """
    从PPTX文件生成SSML内容并保存到指定路径。

    参数:
        pptx_path (str): 输入的PPTX文件路径。

    返回:
        List[str]: 生成的SSML内容列表。
        List[Dict]: 生成的消息列表。
    """

    # 返回列表
    ssmls = []

    # 初始化AI客户端
    client = aisuite.Client()

    # 系统提示，定义生成SSML的规则
    messages = [
        LLMMessage(role="system").text(PROMPT_PPTX_TO_SSMLS).unwrap(),
    ]

    # 遍历PPTX内容，包括文本、图片、表格和注释
    for texts, images, tables, note in pptx_content_generator(pptx_path):

        # 初始化LLM消息内容
        message = LLMMessage(role="user")
        # 添加PPT内容
        message.text("### 以下是PPT内容 ###\n\n")
        if texts:
            # 添加PPT文本内容
            message.text("### 以下是PPT的文本内容 ###\n\n{}\n\n".format("\n\n".join(texts)))
        if tables:
            # 添加PPT表格内容
            message.text("### 以下是PPT的表格内容(json形式) ###\n\n{}\n\n".format("\n\n".join(tables)))
        if note:
            # 添加PPT注释内容
            message.text("### 以下是PPT的注解 ###\n\n{}\n\n".format(note))
        for image in images:
            # 添加PPT图片内容
            message.image(image)
        # 将用户消息添加到消息列表
        messages.append(message.unwrap())

        # 调用LLM生成SSML内容
        ssml = llm_ssml(client=client, messages=messages)
        # 将生成的SSML添加到SSML列表
        ssmls.append(ssml)

        # 将生成的SSML作为助手的响应添加到消息列表
        messages.append(LLMMessage(role="assistant").text(ssml).unwrap())

    return ssmls, messages


def llm_ssml_conclusion(
    messages: List[Dict],
) -> Tuple[str, List[Dict]]:
    """
    从消息列表中提取SSML总结。

    参数:
        messages (List[Dict]): 消息列表。

    返回:
        str: 生成的SSML总结。
        List[Dict]: 生成的消息列表。
    """
    # 初始化AI客户端
    client = aisuite.Client()
    # 调用LLM生成SSML总结
    messages = messages.copy()
    # 生成PPT内容结束的提示
    messages.append(LLMMessage(role="user").text("### 内容结束，生成一份SSML的总结来结束这个课堂 ###").unwrap())
    # 生成PPT内容的总结
    ssml = llm_ssml(
        client=client,
        messages=messages,
    )
    return ssml, messages


def llm_ssml_answer(
    contexts: Union[str, List[str]],
    question: str,
) -> Tuple[str, List[Dict]]:
    """
    根据上下文和问题生成SSML内容。

    参数:
        contexts (Union[str, List[str]]): 教学上下文，可以是字符串或字符串列表。
        question (str): 学生提出的问题。

    返回:
        str: 生成的SSML内容。
        List[Dict]: 生成的消息列表。
    """
    # 如果上下文是字符串，则转换为列表
    if isinstance(contexts, str):
        contexts = [contexts]

    # 初始化AI客户端
    client = aisuite.Client()

    # 系统提示，定义生成SSML的规则
    messages = [
        LLMMessage(role="system").text(PROMPT_QUESTION_TO_SSMLS).unwrap(),
        (
            LLMMessage(role="user")
            .text("### 以下是之前教学的上下文 ###\n\n{}\n\n".format("\n\n".join(contexts)))
            .text("### 以下是学生提出的问题 ###\n\n{}\n\n".format(question))
            .unwrap()
        ),
    ]

    # 调用LLM生成SSML内容
    answer = llm_ssml(
        client=client,
        messages=messages,
    )

    # 将生成的SSML作为助手的响应添加到消息列表
    messages.append(LLMMessage(role="assistant").text(answer).unwrap())

    # 调用LLM生成SSML内容
    return answer, messages
