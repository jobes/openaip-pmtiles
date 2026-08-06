import os
from pathlib import Path
from huggingface_hub import CommitOperationAdd, HfApi, upload_file

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
    """Upload all raw apt/asp geojson files into the `geojsons/` folder.

    All files are uploaded in a single commit. Uploading each file with its
    own `upload_file()` call creates one commit per file, which quickly
    exhausts the Hugging Face rate limit (HTTP 429 Too Many Requests) when
    there are hundreds of per-country files.
    """
    if not GEOJSONS_DIR.exists():
        print("No geojsons directory found, skipping upload")
        return
    files = sorted(GEOJSONS_DIR.glob("*.geojson"))
    if not files:
        print("No geojson files found in tmp/geojsons, skipping upload")
        return

    operations = [
        CommitOperationAdd(
            path_in_repo=f"geojsons/{path.name}",
            path_or_fileobj=str(path),
        )
        for path in files
    ]

    total_size = sum(path.stat().st_size for path in files)
    print(
        f"Uploading {len(files)} geojson files "
        f"(total {format_size(total_size)}) to {repo_id}/geojsons in a single commit ..."
    )
    for path in files:
        print(f"  {path.name} ({format_size(path.stat().st_size)})")

    HfApi(token=token).create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        operations=operations,
        commit_message="Update raw geojsons",
    )
    print("Upload finished")


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