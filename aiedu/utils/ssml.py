import re
from typing import List


def ssml_to_raw_texts(
    sslm_text: str,
) -> List[str]:
    texts = re.split("<[\s\S]*?>", sslm_text)
    texts = [re.sub(r"\s+", "", t).strip() for t in texts]
    texts = [t for t in texts if t]
    return texts
