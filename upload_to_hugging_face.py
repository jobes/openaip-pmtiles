import os
from pathlib import Path
from huggingface_hub import upload_file

GEOJSONS_DIR = Path("tmp/geojsons")


def format_size(num_bytes: int) -> str:
    """Format a byte count into a human-readable size string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def upload_geojsons(token: str | None, repo_id: str) -> None:
    """Upload all raw apt/asp geojson files into the `geojsons/` folder."""
    if not GEOJSONS_DIR.exists():
        print("No geojsons directory found, skipping upload")
        return
    files = sorted(GEOJSONS_DIR.glob("*.geojson"))
    if not files:
        print("No geojson files found in tmp/geojsons, skipping upload")
        return

    print(f"Uploading {len(files)} geojson files to {repo_id}/geojsons ...")
    for path in files:
        size = path.stat().st_size
        upload_file(
            path_or_fileobj=str(path),
            path_in_repo=f"geojsons/{path.name}",
            repo_id=repo_id,
            repo_type="dataset",
            token=token,
        )
        print(f"  Uploaded {path.name} ({format_size(size)})")

    total_size = sum(path.stat().st_size for path in files)
    print(f"Upload finished: {len(files)} files, total {format_size(total_size)}")


if __name__ == "__main__":
    hf_token = os.environ.get("HF_TOKEN")

    if hf_token:
        print(f"Token found! Token length: {len(hf_token)}")
    else:
        print("No token found")

    upload_file(path_or_fileobj="openaip.pmtiles",
                path_in_repo="openaip.pmtiles",
                repo_id="jobes666/openaip-mptiles",
                repo_type="dataset",
                token=hf_token)

    upload_geojsons(hf_token, "jobes666/openaip-mptiles")