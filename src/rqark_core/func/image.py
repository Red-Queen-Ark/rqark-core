import base64
from pathlib import Path

_MAGIC: tuple[tuple[bytes, str], ...] = ((b'\x89PNG\r\n\x1a\n', 'image/png'), (b'\xff\xd8\xff', 'image/jpeg'), (b'GIF87a', 'image/gif'), (b'GIF89a', 'image/gif'), (b'BM', 'image/bmp'))

_SUFFIX: dict[str, str] = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
    '.heic': 'image/heic',
    '.heif': 'image/heif',
    '.tif': 'image/tiff',
    '.tiff': 'image/tiff',
}


def detect_mime(data: bytes, path: Path | None = None) -> str:
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    if data[4:8] == b'ftyp':
        brand = data[8:12]
        if brand in (b'heic', b'heix', b'hevc', b'hevx'):
            return 'image/heic'
        if brand in (b'heif', b'mif1', b'msf1'):
            return 'image/heif'
    if path is not None and (suffix_mime := _SUFFIX.get(path.suffix.lower())):
        return suffix_mime
    raise ValueError(f'unsupported image format: {path}')


def image_to_data_uri(path: Path) -> str:
    data = path.read_bytes()
    mime = detect_mime(data[:32], path)
    b64 = base64.b64encode(data).decode('utf-8')
    return f'data:{mime};base64,{b64}'
