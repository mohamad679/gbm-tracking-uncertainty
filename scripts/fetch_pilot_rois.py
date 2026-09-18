"""Fetch two pinned GlioTrace ROI members using byte ranges, not the 5.6 GB ZIP.

Offsets and hashes are valid only for Zenodo record 21981544, v1. If any
invariant fails, stop: do not accept a mismatched or silently full download.
"""

import argparse
import binascii
import hashlib
from pathlib import Path
import struct
from urllib.request import Request, urlopen
import zlib
from zipfile import ZipFile


URL = "https://zenodo.org/api/records/21981544/files/Example_data.zip/content"
ROIS = {
    "set67": {
        "path": "Set_67/exp_333_roi_84_stack.npz",
        "start": 1265594790, "end": 1280945281,
        "outer_crc": 0x811CC002,
        "sha256": "7878bdb3541d365e96f504be1e7958f2e3b3cca68783f253a2672e264f718b57",
    },
    "set68": {
        "path": "Set_68/exp_337_roi_63_stack.npz",
        "start": 2963593057, "end": 2976531120,
        "outer_crc": 0xFEAA1922,
        "sha256": "1c40f8519930e023530b4912c826e7e231f2270aa2c15023c21461783e86a265",
    },
}


def unpack_member(body: bytes, expected_crc: int, expected_sha256: str) -> bytes:
    """Unwrap a deflated outer ZIP entry; require checksums at both levels."""
    if len(body) < 30:
        raise ValueError("Truncated ZIP local header")
    signature, _, _, method, _, _, _, _, _, name_len, extra_len = struct.unpack(
        "<IHHHHHIIIHH", body[:30]
    )
    if signature != 0x04034B50 or method != 8:
        raise ValueError("Expected a deflated ZIP local entry")
    offset = 30 + name_len + extra_len
    try:
        data = zlib.decompress(body[offset:], wbits=-15)
    except zlib.error as exc:
        raise ValueError(f"Invalid ZIP entry stream: {exc}") from exc
    if len(data) > 25_000_000:
        raise ValueError("Unexpectedly large ROI member")
    if binascii.crc32(data) != expected_crc:
        raise ValueError("Outer ZIP entry CRC mismatch")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("ROI SHA256 mismatch: stop and re-check the source version")
    return data


def fetch_one(record: dict, root: Path) -> Path:
    destination = root / record["path"]
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() == record["sha256"]:
            print("Already verified:", destination)
            return destination
        raise ValueError(f"Existing file hash mismatch: {destination}")
    first, last = record["start"], record["end"]
    length = last - first + 1
    request = Request(URL, headers={"Range": f"bytes={first}-{last}"})
    with urlopen(request, timeout=90) as response:
        if response.status != 206:
            raise ValueError(f"Server did not honor Range (status {response.status})")
        if not response.headers.get("Content-Range", "").startswith(f"bytes {first}-{last}/"):
            raise ValueError("Unexpected Content-Range")
        body = response.read(length + 1)
    if len(body) != length:
        raise ValueError(f"Wrong byte range length: {len(body)} != {length}")
    data = unpack_member(body, record["outer_crc"], record["sha256"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    with ZipFile(destination) as npz:
        invalid = npz.testzip()
    if invalid is not None:
        destination.unlink()
        raise ValueError(f"Inner NPZ member failed CRC: {invalid}")
    print("Verified:", destination, "bytes:", len(data))
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/glio_trace"))
    parser.add_argument("--only", choices=ROIS, help="Fetch just one of the two pilot ROIs")
    args = parser.parse_args()
    records = [ROIS[args.only]] if args.only else ROIS.values()
    for record in records:
        fetch_one(record, args.output_dir)


if __name__ == "__main__":
    main()
