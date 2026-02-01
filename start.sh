python main.py
tippecanoe \
  -o openaip.mbtiles \
  --no-feature-limit \
  --no-tile-size-limit \
  --no-line-simplification \
  --detect-shared-borders \
  --minimum-zoom=0 \
  --maximum-zoom=14 \
  --force \
  --drop-rate=0 \
  --base-zoom=0 \
  --preserve-point-density-threshold=0 \
  --progress-interval=1 \
  --coalesce-smallest-as-needed \
  tmp/airspaces.geojson \
  tmp/rc_airfields.geojson \
  tmp/rc_airspaces.geojson \
  tmp/hang_glidings.geojson \
  tmp/airports.geojson \
  tmp/navaids.geojson \
  tmp/hotspots.geojson \
  tmp/airspaces.geojson \
  tmp/reporting_points.geojson \
  tmp/airspaces_border_offset.geojson \
  tmp/airspaces_border_offset_2x.geojson

python /home/vjoba/Develop/aviation-mock-servers/mbtiles-server.py --mbtiles openaip.mbtiles