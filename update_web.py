from __future__ import annotations

from datetime import date
from pathlib import Path


def update_generated_date() -> None:
	"""Replace the {{GENERATED_DATE}} placeholder in index.html with today's date.

	The date is written in a human-friendly format, e.g. "09 February 2026".
	"""

	index_path = Path(__file__).with_name("index.html")

	if not index_path.exists():
		return

	html = index_path.read_text(encoding="utf-8")

	if "{{GENERATED_DATE}}" not in html:
		# Nothing to replace; avoid rewriting the file unnecessarily.
		return

	today_str = date.today().strftime("%d %B %Y")
	updated_html = html.replace("{{GENERATED_DATE}}", today_str)

	index_path.write_text(updated_html, encoding="utf-8")


if __name__ == "__main__":
	update_generated_date()

