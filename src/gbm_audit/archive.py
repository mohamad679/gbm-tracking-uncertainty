"""Defensive ZIP validation helpers for external benchmark archives."""

from zipfile import ZipFile, ZipInfo

from gbm_audit.config import (
    MAX_ZIP_COMPRESSION_RATIO,
    MAX_ZIP_MEMBER_BYTES,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES,
)


def validate_zip_archive(archive: ZipFile) -> None:
    """Reject archives with unsafe member counts, sizes or compression ratios."""
    members = archive.infolist()
    if len(members) > MAX_ZIP_MEMBERS:
        raise ValueError(f"ZIP contains too many members: {len(members)} > {MAX_ZIP_MEMBERS}")
    total = 0
    for info in members:
        if info.is_dir():
            continue
        if info.file_size < 0 or info.compress_size < 0:
            raise ValueError(f"ZIP member has invalid size metadata: {info.filename}")
        if info.file_size > MAX_ZIP_MEMBER_BYTES:
            raise ValueError(
                f"ZIP member is too large: {info.filename} ({info.file_size} bytes > {MAX_ZIP_MEMBER_BYTES})"
            )
        total += info.file_size
        if total > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError(
                "ZIP total uncompressed size exceeds safety limit: "
                f"{total} > {MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES}"
            )
        if info.file_size and info.compress_size == 0:
            raise ValueError(f"ZIP member has zero compressed size: {info.filename}")
        if info.compress_size:
            ratio = info.file_size / info.compress_size
            if ratio > MAX_ZIP_COMPRESSION_RATIO:
                raise ValueError(
                    f"ZIP member compression ratio is too high: {info.filename} ({ratio:.1f}x)"
                )


def read_member_bytes(archive: ZipFile, member: str | ZipInfo) -> bytes:
    """Read one member after validating its declared uncompressed size."""
    info = archive.getinfo(member) if isinstance(member, str) else member
    if info.file_size > MAX_ZIP_MEMBER_BYTES:
        raise ValueError(
            f"ZIP member is too large: {info.filename} ({info.file_size} bytes > {MAX_ZIP_MEMBER_BYTES})"
        )
    data = archive.read(info)
    if len(data) != info.file_size:
        raise ValueError(f"ZIP member size mismatch after decompression: {info.filename}")
    return data
