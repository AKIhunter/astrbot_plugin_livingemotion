"""Mood cover images maintained by the administrator.

One folder, one file family per mood: ``开心.png``, ``开心-2.webp`` …
The mood key (``happy``) maps to a fixed Chinese stem so a user can drop in
``开心.png`` by hand and see it immediately, without touching the config.

Nothing here is served publicly: the console returns a bounded data URL after
the caller has been authenticated by the HTTP layer.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from pathlib import Path

# 情绪键 → 文件名主干。与前端 AFFECT_LABELS 的顺序无关，改动只影响文件名。
MOOD_STEMS = {
    "calm": "平静", "neutral": "平常", "happy": "开心", "joyful": "喜悦",
    "sad": "悲伤", "anxious": "焦虑", "angry": "愤怒", "tired": "疲惫",
    "excited": "兴奋", "caring": "关切", "lonely": "孤独", "content": "满足",
    "strained": "紧绷", "tense": "紧张", "concerned": "担忧", "subdued": "低落",
    "alert": "警觉", "seeking_company": "渴望陪伴",
}
MOOD_NAMES = {key: stem for key, stem in MOOD_STEMS.items()}
EXTENSIONS = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
MAX_BYTES = 512 * 1024
MAX_FILES_PER_MOOD = 6
SUFFIX = re.compile(r"^(?P<stem>[^-]+)(?:-(?P<index>[2-9]))?\.(?P<ext>png|jpe?g|webp)$", re.IGNORECASE)


class EmotionImageError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


@dataclass(frozen=True)
class StoredImage:
    mood: str
    name: str
    index: int
    updated_at: float
    size: int


class EmotionImages:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory) / "emotion-images"

    def _mood(self, mood) -> str:
        if not isinstance(mood, str) or mood not in MOOD_STEMS:
            raise EmotionImageError("validation_error", "未知的情绪名称。")
        return mood

    def _files(self, mood: str) -> list[StoredImage]:
        stem = MOOD_STEMS[mood]
        found: list[StoredImage] = []
        try:
            entries = list(self.directory.iterdir())
        except (FileNotFoundError, NotADirectoryError):
            return found
        except OSError as error:
            raise EmotionImageError("unavailable", "情绪图片目录不可读。") from error
        for item in entries:
            if not item.is_file():
                continue
            match = SUFFIX.match(item.name)
            if not match or match.group("stem") != stem:
                continue
            try:
                stat = item.stat()
            except OSError:
                continue
            found.append(StoredImage(mood, item.name, int(match.group("index") or 1),
                                     round(stat.st_mtime, 3), stat.st_size))
        return sorted(found, key=lambda image: (image.index, image.name))

    def list(self) -> dict:
        moods = []
        for key, stem in MOOD_STEMS.items():
            files = self._files(key)
            moods.append({"key": key, "name": stem, "count": len(files),
                          "files": [{"name": item.name, "index": item.index,
                                     "bytes": item.size, "updated_at": item.updated_at}
                                    for item in files]})
        return {"api_version": 1, "moods": moods, "max_bytes": MAX_BYTES,
                "max_files": MAX_FILES_PER_MOOD,
                "extensions": sorted(EXTENSIONS), "writable": self._writable()}

    def _writable(self) -> bool:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return True

    def read(self, mood, index=None):
        """Return ``(mime, base64)`` for one image; ``index`` defaults to the first."""
        mood = self._mood(mood)
        files = self._files(mood)
        if not files:
            return None
        wanted = files[0] if index is None else next(
            (item for item in files if item.index == index), None)
        if wanted is None:
            return None
        path = self.directory / wanted.name
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise EmotionImageError("unavailable", "情绪图片读取失败。") from error
        mime = EXTENSIONS.get(path.suffix.lstrip(".").lower(), "application/octet-stream")
        return mime, base64.b64encode(raw).decode("ascii"), wanted.updated_at

    def save(self, mood, data_url) -> StoredImage:
        """Store an uploaded image; replaces the slot it lands on."""
        mood = self._mood(mood)
        mime, raw = _decode(data_url)
        ext = next((name for name, value in EXTENSIONS.items() if value == mime), None)
        if ext is None:
            raise EmotionImageError("validation_error", "只支持 PNG、JPEG 与 WebP 图片。")
        if len(raw) > MAX_BYTES:
            raise EmotionImageError("validation_error", "图片超过 512 KB，请先压缩。")
        if not _looks_like_image(raw, mime):
            raise EmotionImageError("validation_error", "文件内容不是有效的图片。")
        if not self._writable():
            raise EmotionImageError("unavailable", "情绪图片目录不可写。")
        stem = MOOD_STEMS[mood]
        existing = self._files(mood)
        used = {item.index for item in existing}
        slot = next((index for index in range(1, MAX_FILES_PER_MOOD + 1) if index not in used), None)
        if slot is None:
            # 已满：覆盖第一张，保证上传一定有可见结果。
            slot = 1
        name = f"{stem}.{ext}" if slot == 1 else f"{stem}-{slot}.{ext}"
        # 同一槽位换格式（png → webp）时清掉旧文件，避免两张图并存。
        for item in existing:
            if item.index == slot and item.name != name:
                try:
                    (self.directory / item.name).unlink()
                except OSError:
                    pass
        target = self.directory / name
        temporary = self.directory / f".{name}.tmp"
        try:
            temporary.write_bytes(raw)
            temporary.replace(target)
        except OSError as error:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise EmotionImageError("unavailable", "情绪图片保存失败。") from error
        stat = target.stat()
        return StoredImage(mood, name, slot, round(stat.st_mtime, 3), stat.st_size)

    def delete(self, mood, index=None) -> int:
        mood = self._mood(mood)
        files = self._files(mood)
        targets = files if index is None else [item for item in files if item.index == index]
        removed = 0
        for item in targets:
            try:
                (self.directory / item.name).unlink()
                removed += 1
            except FileNotFoundError:
                continue
            except OSError as error:
                raise EmotionImageError("unavailable", "情绪图片删除失败。") from error
        return removed


def _decode(data_url) -> tuple[str, bytes]:
    if not isinstance(data_url, str) or len(data_url) > MAX_BYTES * 2:
        raise EmotionImageError("validation_error", "图片数据缺失或过大。")
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", data_url)
    if not match:
        raise EmotionImageError("validation_error", "只支持 PNG、JPEG 与 WebP 图片。")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as error:
        raise EmotionImageError("validation_error", "图片编码无效。") from error
    return match.group(1), raw


def _looks_like_image(raw: bytes, mime: str) -> bool:
    if mime == "image/png":
        return raw.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return raw.startswith(b"\xff\xd8\xff")
    if mime == "image/webp":
        return raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
    return False
