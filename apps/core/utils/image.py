import io
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile

try:
    from PIL import Image
except ImportError:
    raise ImportError("Pillow is required. Add it to requirements.txt: pip install Pillow")

_ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp")


@dataclass
class ImageConfig:
    max_width: int
    max_height: int
    max_file_size_mb: float = 5.0
    allowed_types: tuple = field(default_factory=lambda: _ALLOWED_TYPES)
    output_format: str = "JPEG"
    quality: int = 85


# Pre-built configs — use directly or use as reference for custom ones
PROFILE_PICTURE_CONFIG = ImageConfig(max_width=400, max_height=400)
THUMBNAIL_CONFIG       = ImageConfig(max_width=150, max_height=150, quality=80)
BANNER_CONFIG          = ImageConfig(max_width=1200, max_height=400)


def process_image(file, config: ImageConfig) -> InMemoryUploadedFile:
    """
    Validate and resize an uploaded image file.

    - Never upscales — only resizes down if the image exceeds config dimensions.
    - Preserves aspect ratio.
    - Normalizes to RGB (handles PNG transparency, CMYK, palette modes).
    """
    content_type = getattr(file, "content_type", "")
    if content_type not in config.allowed_types:
        raise ValidationError(
            f"Unsupported image format. Allowed: {', '.join(config.allowed_types)}"
        )

    if file.size > config.max_file_size_mb * 1024 * 1024:
        raise ValidationError(
            f"Image exceeds the maximum allowed size of {config.max_file_size_mb}MB."
        )

    img = Image.open(file)

    if img.mode != "RGB":
        img = img.convert("RGB")

    # thumbnail() respects aspect ratio and never upscales
    img.thumbnail((config.max_width, config.max_height), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format=config.output_format, quality=config.quality, optimize=True)
    buffer.seek(0)

    ext = config.output_format.lower()
    original_name = getattr(file, "name", "image")
    base_name = original_name.rsplit(".", 1)[0]

    return InMemoryUploadedFile(
        file=buffer,
        field_name="ImageField",
        name=f"{base_name}.{ext}",
        content_type=f"image/{ext}",
        size=buffer.getbuffer().nbytes,
        charset=None,
    )
