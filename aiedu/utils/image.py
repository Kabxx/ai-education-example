import base64
import io
from PIL import Image


def image_compress(
    image: Image.Image,
    quality: int = 50,
) -> Image.Image:
    image_bytes = io.BytesIO()
    image.save(image_bytes, format=image.format, quality=quality)
    image_bytes.seek(0)
    return Image.open(image_bytes)


def image_to_base64_url(
    image: Image.Image,
) -> str:
    image_bytes = io.BytesIO()
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(image_bytes, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(image_bytes.getvalue()).decode()}"
