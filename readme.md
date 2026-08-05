# openaip-pmtiles

Python toolkit for downloading OpenAIP GeoJSON datasets for every supported country, enriching their attributes, and compiling them into per-country PMTiles archives (plus a global combined archive) using Mapbox's tippecanoe utilities.

## Features

- Fetches all OpenAIP dataset slices (airspaces, airports, navaids, obstacles, etc.) per country via HTTPS.
- Normalizes geometry and properties to a PMTiles-friendly schema using `mapper.py` utilities (Shapely + pyproj).
- Generates one GeoJSON file per dataset per country under `tmp/<country>/` to make debugging easier.
- Builds per-country PMTiles (`output_tiles/<country>.pmtiles`) and merges them into `output_tiles/openaip.pmtiles` via `tile-join`.
- Provides progress, timing, and size reporting so long-running runs remain observable.

## Repository Layout

- `main.py` – Orchestrates downloads, per-country processing, and final PMTiles merge.
- `mapper.py` – Maps raw OpenAIP properties/geometries to the simplified dataset schema; applies border buffering for airspaces.
- `enums.py` – Enumerations that mirror OpenAIP categorical values (airspace types, airport types, height units, etc.).
- `countries.py` – ISO country codes that define the processing workload.
- `tmp/` – Created at runtime; holds intermediate GeoJSON files grouped by country.
- `output_tiles/` – Created at runtime; stores all generated PMTiles including the combined `openaip.pmtiles`.

## Requirements

- Python 3.10+
- System packages: `tippecanoe` (provides `tippecanoe` and `tile-join` executables)
- Python packages: `requests`, `shapely`, `pyproj`

### Installing tippecanoe

| Platform      | Command                                                                                        |
| ------------- | ---------------------------------------------------------------------------------------------- |
| Debian/Ubuntu | `sudo apt install tippecanoe` via the [Mapbox PPA](https://github.com/mapbox/tippecanoe#linux) |
| macOS         | `brew install tippecanoe`                                                                      |
| Other         | Build from source per the [upstream README](https://github.com/mapbox/tippecanoe)              |

### Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests shapely pyproj google-auth
```

## Google Cloud authentication

The source bucket is a **requester-pays** bucket, so every download must be
authenticated and must name the billing project that pays for the transfer.

- The billing project is configured via the `GCS_USER_PROJECT` environment
  variable (or a local `.env` file, which is git-ignored):

  ```bash
  export GCS_USER_PROJECT='YOUR_GCP_PROJECT_ID'
  ```

- Never hardcode the project ID in the code — it is loaded from the
  environment so it never ends up in version control.

### Local setup (Application Default Credentials)

Authenticate once on your machine, then the script reuses the credentials:

```bash
# option 1 (recommended):
gcloud auth application-default login

# option 2: use a service-account JSON key (keep the file out of the repo)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### GitHub Actions (Workload Identity Federation)

The workflow `.github/workflows/generate-pmtiles.yml` authenticates via **WIF
(OIDC)** — no long-lived keys are stored. This is safe for a public repo.

One-time setup in the [Google Cloud Console](https://console.cloud.google.com):

1. **Create a service account**, e.g. `gh-actions-sa` in project
   `YOUR_GCP_PROJECT_ID`.
2. Grant it a role that can read the bucket, e.g. `Storage Object Viewer`
   (`roles/storage.objectViewer`), plus `Service Usage Consumer`
   (`roles/serviceusage.serviceUsageConsumer`) so it can use `userProject`.
3. **Create a Workload Identity Pool** (IAM & Admin → Workload Identity
   Federation → Create Pool).
4. **Add an OIDC provider** in that pool:
   - Issuer: `https://token.actions.githubusercontent.com`
   - Audience (allowed audiences): set to the provider name (default matches
     the auto-generated audience of the `google-github-actions/auth` action)
   - Attribute mapping (defaults work):
     `google.subject=assertion.sub`,
     `attribute.repository=assertion.repository`
   - Attribute condition:
     `assertion.repository_owner == "jobes"`
5. **Grant the service account** the `Workload Identity User`
   (`roles/iam.workloadIdentityUser`) role for the pool, restricted to
   `attribute.repository == "jobes/openaip-pmtiles"`.

Then add these **GitHub secrets** (Settings → Secrets and variables → Actions):

| Secret                           | Value                                                                                          |
| -------------------------------- | ---------------------------------------------------------------------------------------------- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | e.g. `projects/123456789/locations/global/workloadIdentityPools/gh-pool/providers/gh-provider` |
| `GCP_SERVICE_ACCOUNT`            | e.g. `gh-actions-sa@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com`                               |
| `GCS_USER_PROJECT`               | `YOUR_GCP_PROJECT_ID`                                                                          |

## Usage

1. Ensure `tippecanoe` and `tile-join` are on your `PATH`.
2. (Optional) Activate your Python virtual environment.
3. Run the pipeline:
   ```bash
   python main.py
   ```
4. Monitor stdout for per-country progress. Intermediate GeoJSON lives in `tmp/<country>/`. Finished PMTiles live in `output_tiles/`.

The script downloads every dataset for every country listed in `countries.py`. Depending on connection speed and compute resources this can take hours. Ctrl+C is safe; rerunning resumes by overwriting per-country artifacts.

## Customization Tips

- **Limit the workload:** Edit `countries.py` to keep only the ISO codes you care about.
- **Add/remove datasets:** Modify the `OPEN_AIP_DATASETS` list in `main.py` to plug in new layers or disable existing ones. Each entry can specify custom `properties_mapper` and `geometry_mapper` callables from `mapper.py`.
- **Change buffering logic:** Adjust `get_airspace_borders_geometry` / `get_airspace_borders2x_geometry` in `mapper.py` if you need different offset distances.

## Troubleshooting

- _`tippecanoe executable not found`_ – Install tippecanoe and ensure the binary directory is on your `PATH`.
- _`Bucket is a requester pays bucket but no user project provided`_ – The request is missing `userProject`. Make sure `GCS_USER_PROJECT` is set (see “Google Cloud authentication”).
- _`401 Unauthorized` when downloading_ – Requester-pays buckets reject anonymous requests. Authenticate locally (ADC) or set up WIF for GitHub Actions (see “Google Cloud authentication”).
- _`No Google Cloud credentials found`_ – Set up Application Default Credentials or, in CI, check the `google-github-actions/auth` step and the two secrets.
- _`requests.exceptions.HTTPError`_ – The OpenAIP API may be temporarily unavailable, or a dataset for a given country/file combination may have been removed. The script logs 404s and keeps going.
- _Slow processing_ – Tippecanoe is CPU heavy. Reduce `COUNTRIES` count or tweak `TIPPECANOE_ARGS` (e.g., raise `--drop-rate`) to finish faster.

## Output

- Combined global tileset: `output_tiles/openaip.pmtiles`
- Daily generated global pmtiles available on https://jobes.github.io/openaip-pmtiles/

These PMTiles archives can be hosted directly (e.g., Cloudflare R2, S3) or streamed via PMTiles-aware clients like MapLibre GL JS.
