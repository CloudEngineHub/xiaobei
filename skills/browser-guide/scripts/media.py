#!/usr/bin/env python3
"""Prepare upload copies and crop genuine screenshots; never drive a browser."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import uuid


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def stage_upload(args):
    # Use the same state-dir override as the managed browser. An explicit root
    # is required for nonstandard policies; do not guess a /tmp upload root.
    state_dir = Path(os.environ.get("OPENCLAW_STATE_DIR") or Path.home() / ".openclaw")
    root = (Path(args.inbound_root) if args.inbound_root else state_dir / "media/inbound").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve(strict=True)
    outputs = []
    try:
        for value in args.sources:
            source = Path(value).expanduser()
            if not source.is_absolute():
                raise ValueError("source must be an absolute path")
            source = source.resolve(strict=True)
            if not source.is_file() or source.stat().st_size == 0:
                raise ValueError("source must be a nonempty regular file")
            before = source.stat()
            source_hash = digest(source)
            # Exclusive creation prevents overwriting another task's upload.
            fd, name = tempfile.mkstemp(prefix=f"upload-{uuid.uuid4().hex[:12]}-", suffix=source.suffix, dir=root)
            target = Path(name)
            outputs.append(target)
            with os.fdopen(fd, "wb") as destination, source.open("rb") as original:
                shutil.copyfileobj(original, destination)
            after = source.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("source changed while staging; choose a stable final version")
            if target.stat().st_size != before.st_size or digest(target) != source_hash:
                raise ValueError("staged copy does not match source")
        return {"inboundRoot": str(root), "files": [
            {"source": str(Path(source).expanduser().resolve()), "path": str(target),
             "bytes": target.stat().st_size, "sha256": digest(target)}
            for source, target in zip(args.sources, outputs)
        ]}
    except BaseException:
        for target in outputs:
            target.unlink(missing_ok=True)
        raise


def crop_evidence(args):
    from PIL import Image

    source = Path(args.source).expanduser().resolve(strict=True)
    output = Path(args.output).expanduser().absolute()
    if output.resolve() == source or output.exists():
        raise ValueError("output must be a new file, distinct from the screenshot")
    geometry = json.loads(Path(args.geometry).read_text(encoding="utf-8"))
    # Coordinates are relative to the saved screenshot's origin in CSS pixels.
    # Measure its CSS width/height at capture time; DPR alone is insufficient.
    keys = ("captureWidth", "captureHeight", "x", "y", "width", "height")
    values = {key: float(geometry[key]) for key in keys}
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError("geometry must be finite")
    cw, ch, x, y, width, height = (values[key] for key in keys)
    if min(cw, ch, width, height) <= 0 or min(x, y) < 0 or x + width > cw or y + height > ch:
        raise ValueError("crop lies outside the captured CSS rectangle")
    with Image.open(source) as screenshot:
        sx, sy = screenshot.width / cw, screenshot.height / ch
        if abs(sx - sy) > max(sx, sy) * 0.01:
            raise ValueError("screenshot and CSS capture dimensions disagree; remeasure")
        box = (math.floor(x * sx), math.floor(y * sy),
               math.ceil((x + width) * sx), math.ceil((y + height) * sy))
        output.parent.mkdir(parents=True, exist_ok=True)
        # PNG preserves the original pixels. Do not resize, repaint or remove UI.
        with output.open("xb") as stream:
            screenshot.crop(box).save(stream, format="PNG")
    return {"source": str(source), "path": str(output), "pixelBox": box,
            "sourceSha256": digest(source), "sha256": digest(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage-upload", help="copy final files into direct inbound children")
    stage.add_argument("sources", nargs="+")
    stage.add_argument("--inbound-root", help="actual inbound root declared by the tool")
    stage.set_defaults(run=stage_upload)
    crop = commands.add_parser("crop-evidence", help="crop a screenshot using measured CSS geometry")
    crop.add_argument("--source", required=True)
    crop.add_argument("--geometry", required=True)
    crop.add_argument("--output", required=True)
    crop.set_defaults(run=crop_evidence)
    args = parser.parse_args()
    try:
        print(json.dumps(args.run(args), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, ImportError) as error:
        parser.exit(1, f"browser-guide: {error}\n")


if __name__ == "__main__":
    main()
