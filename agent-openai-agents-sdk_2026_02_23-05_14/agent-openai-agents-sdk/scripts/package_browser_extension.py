from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import json


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    extension_dir = project_root / "browser-extension"
    manifest_path = extension_dir / "manifest.json"

    if not extension_dir.exists() or not manifest_path.exists():
        raise SystemExit("browser-extension/manifest.json not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest.get("version", "0.1.0"))

    dist_dir = project_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    output_zip = dist_dir / f"perfect-agent-browser-extension-v{version}.zip"

    with ZipFile(output_zip, mode="w", compression=ZIP_DEFLATED) as zf:
        for file in extension_dir.rglob("*"):
            if not file.is_file():
                continue
            relative = file.relative_to(extension_dir)
            zf.write(file, relative.as_posix())

    print(f"Created: {output_zip}")


if __name__ == "__main__":
    main()
