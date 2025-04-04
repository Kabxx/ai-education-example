import os


import csv
import os.path
import pickle
import itertools
from collections import namedtuple, OrderedDict
from dataclasses import dataclass
from enum import Enum
import sys
from typing import Dict, Iterable, List, IO, Optional

import jieba
import jieba.analyse


DICT_FILE_NAME = "dict.csv"
PKL_FILE_NAME = "words.pkl"


# 情感分类: 7 大类, 21 小类
_categories = {
    "happiness": ["PA", "PE"],  # 乐
    "goodness": ["PD", "PH", "PG", "PB", "PK"],  # 好
    "anger": ["NA"],  # 怒
    "sadness": ["NB", "NJ", "NH", "PF"],  # 哀
    "fear": ["NI", "NC", "NG"],  # 惧
    "dislike": ["NE", "ND", "NN", "NK", "NL"],  # 恶
    "surprise": ["PC"],  # 惊
}

# 所有 21 小类情感
_emotions = (
    _categories["happiness"]
    + _categories["goodness"]
    + _categories["anger"]
    + _categories["sadness"]
    + _categories["fear"]
    + _categories["dislike"]
    + _categories["surprise"]
)

# 21 小类情感映射到 valence-arousal 空间
_va_space = {
    "PA": [0.7, 0.7],
    "PE": [0.7, 0.3],
    "PD": [0.53, 0.47],
    "PH": [0.6, 0.6],
    "PG": [0.67, 0.43],
    "PB": [0.67, 0.57],
    "PK": [0.6, 0.4],
    "NA": [0.37, 0.77],
    "NB": [0.33, 0.43],
    "NJ": [0.3, 0.7],
    "NH": [0.4, 0.4],
    "PF": [0.53, 0.27],
    "NI": [0.33, 0.57],
    "NC": [0.3, 0.7],
    "NG": [0.37, 0.5],
    "NE": [0.47, 0.67],
    "ND": [0.4, 0.6],
    "NN": [0.43, 0.57],
    "NK": [0.43, 0.47],
    "NL": [0.4, 0.43],
    "PC": [0.63, 0.77],
}


class _PolarityEnum(Enum):
    """极性标注

    每个词在每一类情感下都对应了一个极性。其中，0代表中性，1代表褒义，2代表贬义，3代表兼有褒贬两性。
    注：褒贬标注时，通过词本身和情感共同确定，所以有些情感在一些词中可能极性1，而其他的词中有可能极性为0。
    """

    neutrality = 0
    positive = 1
    negative = 2
    both = 3


@dataclass
class _Word:
    """一个词
    lex + emotion 确定一个 Word，
    一个词多个 emotion 视为多个不同的 Word。
    """

    word: str
    emotion: str
    intensity: int  # 情感强度: 分为 1, 3, 5, 7, 9 五档，9 表示强度最大，1 为强度最小。
    polarity: _PolarityEnum

    # ['词语', '词性种类', '词义数', '词义序号', '情感分类',
    #  '强度', '极性', '辅助情感分类', '强度', '极性']
    DictRow = namedtuple("DictRow", ["word", "kind", "means", "mean", "emotion", "intensity", "polarity", "emotion2", "intensity2", "polarity2"])

    @staticmethod
    def from_strs(word: str, emotion: str, intensity: str, polarity: str):
        word = word.strip()
        emotion = emotion.strip()

        intensity = int(intensity or 1)
        intensity = intensity if intensity >= 1 else 1
        intensity = intensity if intensity <= 9 else 9

        polarity = int(polarity or 0)
        polarity = polarity if polarity >= 0 else 0
        polarity = polarity if polarity <= 4 else 0

        return _Word(word, emotion, intensity, _PolarityEnum(polarity))


class _EmotionCountResult:
    """一个情感分析的结果

    emotions: {'情感': 出现次数*情感强度}
    polarity: 整句话的极性: {'褒|贬': 出现次数}
    valance_arouse: 整句话的 valance-arouse 值: [valance, arouse]
    """

    emotions: OrderedDict
    polarity: OrderedDict
    # TODO: 注意 typos: valance -> valence, arouse -> arousal
    valance_arouse: list

    def __init__(self):
        # OrderedDict([('PA', 0), ('PE', 0), ('PD', 0), ...])
        self.emotions = OrderedDict.fromkeys(_emotions, 0)
        # OrderedDict([(<Polarity.neutrality: 0>, 0), (<Polarity.positive: 1>, 0), ...])
        self.polarity = OrderedDict.fromkeys(_PolarityEnum, 0)
        # [valance,arouse]
        self.valance_arouse = []

    def emotions_va(self) -> list:
        """计算并返回 valance-arouse 值: [valance, arouse]"""
        valance = 0
        arouse = 0
        cnt = 0

        # [[emotion percent, valance, arouse]]
        self.valance_arouse = [[value] + _va_space[key] for key, value in self.emotions.items() if value != 0]
        # print(self.valance_arouse)

        # sort by intensity
        self.valance_arouse.sort(key=lambda x: x[0])

        sum_intensity = sum(map(lambda x: x[0], self.valance_arouse))

        if sum_intensity == 0:
            self.valance_arouse = [0.5, 0.5]
            return self.valance_arouse

        # 取出强度贡献前 50% 的情感的 v, a 分量
        sum_percent = 0
        valances, arouses = [], []
        for intensity, v, a in self.valance_arouse:
            percent = intensity / sum_intensity

            valances.append(v)
            arouses.append(a)

            sum_percent += percent
            if sum_percent > 0.5:
                break

        v = va_component_sum(valances)
        a = va_component_sum(arouses)

        self.valance_arouse = [v, a]
        return self.valance_arouse


def va_component_sum(values: Iterable[float], weights: Optional[Iterable[float]] = None) -> float:
    """这个函数用来求 valence 或 arousal 的矢量和。

    v, a 的值被表示为位于 (0, 0) 到 (1, 1) 的笛卡尔系中的点 (x, y)，
    但是他们的含义是从 (0.5, 0.5) 指向 (x, y) 的**向量**。

    所以多个情感值 (v, a) 的叠加不能简单地数字加权求和平均。反例：

        VA(0.7, 0.7) + VA(0.7, 0.3) = VA((0.7 + 0.7) / 2, (0.7 + 0.3) / 2) = VA(0.7, 0.5)

    两个高 V 值叠加应该更高，但这种算法*只会减损，不能增益*。
    正确的做法应该需要坐标变换，在 V-A 的向量空间中，进行矢量加法：

        VA(0.7, 0.7) + VA(0.7, 0.3) = VA(0.9, 0.5)

    这里具体的算法是：

       (x, y) + (u, v) = (x-0.5, y-0.5) +  (u-0.5, v-0.5) + (0.5, 0.5) = (x+u-0.5, y+v-0.5)

    即先做变换 (x - 0.5, y - 0.5)，之后运算，然后再逆变换 (x + 0.5, y + 0.5)。

    ⚠️  不要传 weight 参数！向量和不知道咋加权。
       这里计算情感加权，感觉是要作为模糊向量的隶属度了。
       感觉太麻烦，就不要了吧。
    """
    if not weights:
        weights = itertools.repeat(1.0)  # [1, 1, ...]

    sum_v = 0  # 加权和
    # sum_w = 0  # 权之和
    sum_n = 0  # 被加数的量

    for v, w in zip(values, weights):
        v = v - 0.5  # 座标变换: (0.0, 0.0) -> (0.5, 0.5)

        sum_n += 1
        sum_v += v * w
        # sum_w += w

    if sum_n == 0:
        return 0.5

    # sum_v /= sum_w  # intensity normalization
    sum_v += 0.5  # 座标变换: (0.5, 0.5) -> (0.0, 0.0)

    if sum_v < 0:
        return 0.0
    if sum_v > 1:
        return 1.0

    return sum_v


class _EmoText:
    """该类使用大连理工大学七大类情绪词典作为情绪分析的情绪词库，对文本进行细粒度情感分析。

    +------+--------------+----------+--------------------------------+
    |      | 表2 情感分类 |          |                                |
    +------+--------------+----------+--------------------------------+
    | 编号 | 情感大类     | 情感类   | 例词                           |
    +------+--------------+----------+--------------------------------+
    | 1    | 乐           | 快乐(PA) | 喜悦、欢喜、笑眯眯、欢天喜地   |
    +------+--------------+----------+--------------------------------+
    | 2    |              | 安心(PE) | 踏实、宽心、定心丸、问心无愧   |
    +------+--------------+----------+--------------------------------+
    | 3    | 好           | 尊敬(PD) | 恭敬、敬爱、毕恭毕敬、肃然起敬 |
    +------+--------------+----------+--------------------------------+
    | 4    |              | 赞扬(PH) | 英俊、优秀、通情达理、实事求是 |
    +------+--------------+----------+--------------------------------+
    | 5    |              | 相信(PG) | 信任、信赖、可靠、毋庸置疑     |
    +------+--------------+----------+--------------------------------+
    | 6    |              | 喜爱(PB) | 倾慕、宝贝、一见钟情、爱不释手 |
    +------+--------------+----------+--------------------------------+
    | 7    |              | 祝愿(PK) | 渴望、保佑、福寿绵长、万寿无疆 |
    +------+--------------+----------+--------------------------------+
    | 8    | 怒           | 愤怒(NA) | 气愤、恼火、大发雷霆、七窍生烟 |
    +------+--------------+----------+--------------------------------+
    | 9    | 哀           | 悲伤(NB) | 忧伤、悲苦、心如刀割、悲痛欲绝 |
    +------+--------------+----------+--------------------------------+
    | 10   |              | 失望(NJ) | 憾事、绝望、灰心丧气、心灰意冷 |
    +------+--------------+----------+--------------------------------+
    | 11   |              | 疚(NH)   | 内疚、忏悔、过意不去、问心有愧 |
    +------+--------------+----------+--------------------------------+
    | 12   |              | 思(PF)   | 思念、相思、牵肠挂肚、朝思暮想 |
    +------+--------------+----------+--------------------------------+
    | 13   | 惧           | 慌(NI)   | 慌张、心慌、不知所措、手忙脚乱 |
    +------+--------------+----------+--------------------------------+
    | 14   |              | 恐惧(NC) | 胆怯、害怕、担惊受怕、胆颤心惊 |
    +------+--------------+----------+--------------------------------+
    | 15   |              | 羞(NG)   | 害羞、害臊、面红耳赤、无地自容 |
    +------+--------------+----------+--------------------------------+
    | 16   | 恶           | 烦闷(NE) | 憋闷、烦躁、心烦意乱、自寻烦恼 |
    +------+--------------+----------+--------------------------------+
    | 17   |              | 憎恶(ND) | 反感、可耻、恨之入骨、深恶痛绝 |
    +------+--------------+----------+--------------------------------+
    | 18   |              | 贬责(NN) | 呆板、虚荣、杂乱无章、心狠手辣 |
    +------+--------------+----------+--------------------------------+
    | 19   |              | 妒忌(NK) | 眼红、吃醋、醋坛子、嫉贤妒能   |
    +------+--------------+----------+--------------------------------+
    | 20   |              | 怀疑(NL) | 多心、生疑、将信将疑、疑神疑鬼 |
    +------+--------------+----------+--------------------------------+
    | 21   | 惊           | 惊奇(PC) | 奇怪、奇迹、大吃一惊、瞠目结舌 |
    +------+--------------+----------+--------------------------------+

    (table above: http://sa-nsfc.com/outcome/resource/item-2.html)
    """

    def __init__(self):
        self.pkl_path = os.path.join(os.path.dirname(__file__), "resources", "emotext", PKL_FILE_NAME)
        self.dict_path = os.path.join(os.path.dirname(__file__), "resources", "emotext", DICT_FILE_NAME)
        # self.pkl_path = pathlib.Path(__file__).parent.joinpath(PKL_FILE_NAME)
        # self.dict_path = pathlib.Path(__file__).parent.joinpath(DICT_FILE_NAME)

        self.words = {}  # {"emotion": [words...]}
        if not self._words_from_pkl():
            print(f"[emotext] pkl file unavailable, loading words from {self.dict_path}...", file=sys.stderr)
            self._words_from_dict()
            self._save_words_pkl()
            print(f"[emotext] words loaded from {self.dict_path} -> {self.pkl_path}", file=sys.stderr)

    def _words_from_dict(self):
        self.words = {emo: [] for emo in _emotions}
        with open(self.dict_path, "r", encoding="utf-8") as f:
            self._read_dict(f)

    def _read_dict(self, csvfile: IO):
        reader = csv.reader(csvfile)
        reader.__next__()  # skip header

        for row in reader:
            try:
                r = map(lambda x: x.strip(), row)
                r = _Word.DictRow(*r)
                if r.emotion in _emotions:
                    self.words[r.emotion].append(_Word.from_strs(r.word, r.emotion, r.intensity, r.polarity))
                if r.emotion2 and r.emotion2 in _emotions:
                    self.words[r.emotion].append(_Word.from_strs(r.word, r.emotion2, r.intensity2, r.polarity2))
            except Exception as e:
                print(f"Failed to parse word from dict: {row=}")
                raise e

    def _words_from_pkl(self) -> bool:
        """Fill self.words from the pkl file by self._save_words_pkl()

        XXX: pickle 不安全，但快一些: 读 dict.csv 0.9s, 读 words.pkl 0.7s

        :return: True for read, or False if the pkl file does not exist.
        """
        if not os.path.exists(self.pkl_path):
            return False
        with open(self.pkl_path, "rb") as f:
            try:
                self._read_pkl(f)
            except Exception as e:
                print(f"Failed to read pkl file: {e}")
                return False
        return True

    def _read_pkl(self, pkl_file: IO):
        self.words = pickle.load(pkl_file)

    def _save_words_pkl(self):
        with open(self.pkl_path, "wb") as f:
            pickle.dump(self.words, f)

    def _find_word(self, w: str) -> List[_Word]:
        """在 Emotions.words 中找 w

        :param w: 要找的词
        :return: 找到返回对应的 Word 对象们，找不到返回 []
        """
        result = []
        for emotion, words_of_emotion in self.words.items():
            ws = list(map(lambda x: x.word, words_of_emotion))
            if w in ws:
                result.append(words_of_emotion[ws.index(w)])
        return result

    def emotion_count(self, text) -> _EmotionCountResult:
        """简单情感分析。计算各个情绪词 出现次数 * 强度

        :param text:  中文文本字符串
        :return: 返回文本情感统计信息 EmotionCountResult

        """
        result = _EmotionCountResult()

        # words = jieba.cut(text)
        keywords = jieba.analyse.extract_tags(text, withWeight=True)

        for word, weight in keywords:
            for w in self._find_word(word):
                result.emotions[w.emotion] += w.intensity * weight
                result.polarity[w.polarity] += weight

        return result


_emotext = _EmoText()


def emotion(
    text: str,
) -> Dict:
    result = _emotext.emotion_count(text)
    result_emotions = {key: value for key, value in result.emotions.items() if value != 0}
    result_polarity = {key.name: value for key, value in result.polarity.items() if value != 0}
    va = result.emotions_va() or [0.5, 0.5]
    result_va = {"valence": va[0], "arousal": va[1]}
    return {
        "emotions": result_emotions,
        "polarity": result_polarity,
        "va": result_va,
    }
