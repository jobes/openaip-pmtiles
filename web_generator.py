"""Generate the static GeoJSON download page (web/geojsons.html).

The page lists every country from countries.py together with its raw
OpenAIP airport/airspace GeoJSON files, which are hosted in the
`geojsons/` folder of the Hugging Face dataset repository.

Regenerate it locally (or via `python update_web.py` in CI) whenever the
country list changes:

    python web_generator.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from countries import countries

REPO_ID = "jobes666/openaip-mptiles"
HF_RESOLVE = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main"
HF_API_TREE = f"https://huggingface.co/api/datasets/{REPO_ID}/tree/main/geojsons"

# Layer metadata used for the two files generated per country.
LAYERS = [
    ("apt", "Airports", "fa-plane-up", "Runways, heliports & airfields"),
    ("asp", "Airspaces", "fa-draw-polygon", "Controlled & special-use airspace"),
]

# Continent sections in the order they should appear on the page.
CONTINENTS = [
    ("Europe", "fa-earth-europe"),
    ("Asia", "fa-earth-asia"),
    ("Africa", "fa-earth-africa"),
    ("North America", "fa-earth-americas"),
    ("South America", "fa-earth-americas"),
    ("Oceania", "fa-earth-oceania"),
    ("Antarctica", "fa-snowflake"),
]

# ISO 3166-1 alpha-2 code -> (English name, continent) for every country
# currently processed by the pipeline.
COUNTRY_META = {
    "ad": ("Andorra", "Europe"), "ae": ("United Arab Emirates", "Asia"),
    "af": ("Afghanistan", "Asia"), "ag": ("Antigua and Barbuda", "North America"),
    "ai": ("Anguilla", "North America"), "al": ("Albania", "Europe"),
    "am": ("Armenia", "Asia"), "ao": ("Angola", "Africa"),
    "aq": ("Antarctica", "Antarctica"), "ar": ("Argentina", "South America"),
    "as": ("American Samoa", "Oceania"), "at": ("Austria", "Europe"),
    "au": ("Australia", "Oceania"), "aw": ("Aruba", "North America"),
    "ax": ("Åland Islands", "Europe"), "az": ("Azerbaijan", "Asia"),
    "ba": ("Bosnia and Herzegovina", "Europe"), "bb": ("Barbados", "North America"),
    "bd": ("Bangladesh", "Asia"), "be": ("Belgium", "Europe"),
    "bf": ("Burkina Faso", "Africa"), "bg": ("Bulgaria", "Europe"),
    "bh": ("Bahrain", "Asia"), "bi": ("Burundi", "Africa"),
    "bj": ("Benin", "Africa"), "bl": ("Saint Barthélemy", "North America"),
    "bm": ("Bermuda", "North America"), "bn": ("Brunei", "Asia"),
    "bo": ("Bolivia", "South America"), "bq": ("Bonaire, Sint Eustatius and Saba", "North America"),
    "br": ("Brazil", "South America"), "bs": ("Bahamas", "North America"),
    "bt": ("Bhutan", "Asia"), "bw": ("Botswana", "Africa"),
    "by": ("Belarus", "Europe"), "bz": ("Belize", "North America"),
    "ca": ("Canada", "North America"), "cc": ("Cocos (Keeling) Islands", "Asia"),
    "cd": ("DR Congo", "Africa"), "cf": ("Central African Republic", "Africa"),
    "cg": ("Republic of the Congo", "Africa"), "ch": ("Switzerland", "Europe"),
    "ci": ("Côte d'Ivoire", "Africa"), "ck": ("Cook Islands", "Oceania"),
    "cl": ("Chile", "South America"), "cm": ("Cameroon", "Africa"),
    "cn": ("China", "Asia"), "co": ("Colombia", "South America"),
    "cr": ("Costa Rica", "North America"), "cu": ("Cuba", "North America"),
    "cv": ("Cape Verde", "Africa"), "cw": ("Curaçao", "North America"),
    "cx": ("Christmas Island", "Asia"), "cy": ("Cyprus", "Asia"),
    "cz": ("Czechia", "Europe"), "de": ("Germany", "Europe"),
    "dj": ("Djibouti", "Africa"), "dk": ("Denmark", "Europe"),
    "dm": ("Dominica", "North America"), "do": ("Dominican Republic", "North America"),
    "dz": ("Algeria", "Africa"), "ec": ("Ecuador", "South America"),
    "ee": ("Estonia", "Europe"), "eg": ("Egypt", "Africa"),
    "eh": ("Western Sahara", "Africa"), "er": ("Eritrea", "Africa"),
    "es": ("Spain", "Europe"), "et": ("Ethiopia", "Africa"),
    "fi": ("Finland", "Europe"), "fj": ("Fiji", "Oceania"),
    "fk": ("Falkland Islands", "South America"), "fm": ("Micronesia", "Oceania"),
    "fo": ("Faroe Islands", "Europe"), "fr": ("France", "Europe"),
    "ga": ("Gabon", "Africa"), "gb": ("United Kingdom", "Europe"),
    "gd": ("Grenada", "North America"), "ge": ("Georgia", "Asia"),
    "gf": ("French Guiana", "South America"), "gg": ("Guernsey", "Europe"),
    "gh": ("Ghana", "Africa"), "gi": ("Gibraltar", "Europe"),
    "gl": ("Greenland", "North America"), "gm": ("Gambia", "Africa"),
    "gn": ("Guinea", "Africa"), "gp": ("Guadeloupe", "North America"),
    "gq": ("Equatorial Guinea", "Africa"), "gr": ("Greece", "Europe"),
    "gt": ("Guatemala", "North America"), "gu": ("Guam", "Oceania"),
    "gw": ("Guinea-Bissau", "Africa"), "gy": ("Guyana", "South America"),
    "hk": ("Hong Kong", "Asia"), "hn": ("Honduras", "North America"),
    "hr": ("Croatia", "Europe"), "ht": ("Haiti", "North America"),
    "hu": ("Hungary", "Europe"), "id": ("Indonesia", "Asia"),
    "ie": ("Ireland", "Europe"), "il": ("Israel", "Asia"),
    "im": ("Isle of Man", "Europe"), "in": ("India", "Asia"),
    "io": ("British Indian Ocean Territory", "Asia"), "iq": ("Iraq", "Asia"),
    "ir": ("Iran", "Asia"), "is": ("Iceland", "Europe"),
    "it": ("Italy", "Europe"), "je": ("Jersey", "Europe"),
    "jm": ("Jamaica", "North America"), "jo": ("Jordan", "Asia"),
    "jp": ("Japan", "Asia"), "ke": ("Kenya", "Africa"),
    "kg": ("Kyrgyzstan", "Asia"), "kh": ("Cambodia", "Asia"),
    "ki": ("Kiribati", "Oceania"), "km": ("Comoros", "Africa"),
    "kn": ("Saint Kitts and Nevis", "North America"), "kp": ("North Korea", "Asia"),
    "kr": ("South Korea", "Asia"), "kw": ("Kuwait", "Asia"),
    "ky": ("Cayman Islands", "North America"), "kz": ("Kazakhstan", "Asia"),
    "la": ("Laos", "Asia"), "lb": ("Lebanon", "Asia"),
    "lc": ("Saint Lucia", "North America"), "li": ("Liechtenstein", "Europe"),
    "lk": ("Sri Lanka", "Asia"), "lr": ("Liberia", "Africa"),
    "ls": ("Lesotho", "Africa"), "lt": ("Lithuania", "Europe"),
    "lu": ("Luxembourg", "Europe"), "lv": ("Latvia", "Europe"),
    "ly": ("Libya", "Africa"), "ma": ("Morocco", "Africa"),
    "mc": ("Monaco", "Europe"), "md": ("Moldova", "Europe"),
    "me": ("Montenegro", "Europe"), "mg": ("Madagascar", "Africa"),
    "mh": ("Marshall Islands", "Oceania"), "mk": ("North Macedonia", "Europe"),
    "ml": ("Mali", "Africa"), "mm": ("Myanmar", "Asia"),
    "mn": ("Mongolia", "Asia"), "mp": ("Northern Mariana Islands", "Oceania"),
    "mq": ("Martinique", "North America"), "mr": ("Mauritania", "Africa"),
    "ms": ("Montserrat", "North America"), "mt": ("Malta", "Europe"),
    "mu": ("Mauritius", "Africa"), "mv": ("Maldives", "Asia"),
    "mw": ("Malawi", "Africa"), "mx": ("Mexico", "North America"),
    "my": ("Malaysia", "Asia"), "mz": ("Mozambique", "Africa"),
    "na": ("Namibia", "Africa"), "nc": ("New Caledonia", "Oceania"),
    "ne": ("Niger", "Africa"), "nf": ("Norfolk Island", "Oceania"),
    "ng": ("Nigeria", "Africa"), "ni": ("Nicaragua", "North America"),
    "nl": ("Netherlands", "Europe"), "no": ("Norway", "Europe"),
    "np": ("Nepal", "Asia"), "nr": ("Nauru", "Oceania"),
    "nu": ("Niue", "Oceania"), "nz": ("New Zealand", "Oceania"),
    "om": ("Oman", "Asia"), "pa": ("Panama", "North America"),
    "pe": ("Peru", "South America"), "pf": ("French Polynesia", "Oceania"),
    "pg": ("Papua New Guinea", "Oceania"), "ph": ("Philippines", "Asia"),
    "pk": ("Pakistan", "Asia"), "pl": ("Poland", "Europe"),
    "pm": ("Saint Pierre and Miquelon", "North America"), "pr": ("Puerto Rico", "North America"),
    "ps": ("Palestine", "Asia"), "pt": ("Portugal", "Europe"),
    "pw": ("Palau", "Oceania"), "py": ("Paraguay", "South America"),
    "qa": ("Qatar", "Asia"), "re": ("Réunion", "Africa"),
    "ro": ("Romania", "Europe"), "rs": ("Serbia", "Europe"),
    "ru": ("Russia", "Europe"), "rw": ("Rwanda", "Africa"),
    "sa": ("Saudi Arabia", "Asia"), "sb": ("Solomon Islands", "Oceania"),
    "sc": ("Seychelles", "Africa"), "sd": ("Sudan", "Africa"),
    "se": ("Sweden", "Europe"), "sg": ("Singapore", "Asia"),
    "sh": ("Saint Helena, Ascension and Tristan da Cunha", "Africa"),
    "si": ("Slovenia", "Europe"), "sk": ("Slovakia", "Europe"),
    "sl": ("Sierra Leone", "Africa"), "sn": ("Senegal", "Africa"),
    "so": ("Somalia", "Africa"), "sr": ("Suriname", "South America"),
    "ss": ("South Sudan", "Africa"), "sv": ("El Salvador", "North America"),
    "sx": ("Sint Maarten", "North America"), "sy": ("Syria", "Asia"),
    "sz": ("Eswatini", "Africa"), "tc": ("Turks and Caicos Islands", "North America"),
    "td": ("Chad", "Africa"), "tg": ("Togo", "Africa"),
    "th": ("Thailand", "Asia"), "tj": ("Tajikistan", "Asia"),
    "tl": ("Timor-Leste", "Asia"), "tm": ("Turkmenistan", "Asia"),
    "tn": ("Tunisia", "Africa"), "to": ("Tonga", "Oceania"),
    "tr": ("Turkey", "Asia"), "tt": ("Trinidad and Tobago", "North America"),
    "tv": ("Tuvalu", "Oceania"), "tw": ("Taiwan", "Asia"),
    "tz": ("Tanzania", "Africa"), "ua": ("Ukraine", "Europe"),
    "ug": ("Uganda", "Africa"), "us": ("United States", "North America"),
    "uy": ("Uruguay", "South America"), "uz": ("Uzbekistan", "Asia"),
    "vc": ("Saint Vincent and the Grenadines", "North America"),
    "ve": ("Venezuela", "South America"), "vg": ("British Virgin Islands", "North America"),
    "vi": ("U.S. Virgin Islands", "North America"), "vn": ("Vietnam", "Asia"),
    "vu": ("Vanuatu", "Oceania"), "wf": ("Wallis and Futuna", "Oceania"),
    "ws": ("Samoa", "Oceania"), "xk": ("Kosovo", "Europe"),
    "ye": ("Yemen", "Asia"), "yt": ("Mayotte", "Africa"),
    "za": ("South Africa", "Africa"), "zm": ("Zambia", "Africa"),
    "zw": ("Zimbabwe", "Africa"),
}


def build_country_card(code: str, name: str) -> str:
    """Render one country card with a download button per layer."""
    code = code.lower()
    buttons = []
    for file_code, label, icon, hint in LAYERS:
        filename = f"{code}_{file_code}.geojson"
        url = f"{HF_RESOLVE}/geojsons/{filename}"
        buttons.append(
            f"""
            <a href="{url}"
               target="_blank" rel="noopener"
               class="group flex items-center gap-3 rounded-lg border border-slate-200
                      bg-slate-50 px-3 py-2.5 hover:border-blue-400 hover:bg-blue-50
                      transition-colors"
               title="{hint}">
              <i class="fa-solid {icon} w-5 text-blue-500 group-hover:text-blue-600"></i>
              <span class="flex-1 text-sm font-medium text-slate-700 group-hover:text-slate-900">
                {label}
              </span>
              <span class="file-size text-xs font-mono text-slate-400"
                    data-file="{filename}">&ndash;</span>
              <i class="fa-solid fa-download text-xs text-slate-300 group-hover:text-blue-500"></i>
            </a>"""
        )
    return f"""
          <div class="country-card card p-4" data-code="{code}" data-name="{name.lower()}">
            <div class="flex items-center justify-between mb-3">
              <span class="font-semibold text-slate-800">{name}</span>
              <span class="text-[11px] font-mono uppercase tracking-wider
                           bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                {code}
              </span>
            </div>
            <div class="grid grid-cols-1 gap-2">
              {''.join(buttons)}
            </div>
          </div>"""


def build_page() -> str:
    today = date.today().strftime("%d %B %Y")
    by_continent: dict[str, list[tuple[str, str]]] = {c: [] for c, _ in CONTINENTS}
    for code in countries:
        meta = COUNTRY_META.get(code.lower(), (code.upper(), "Other"))
        by_continent.setdefault(meta[1], []).append((code.lower(), meta[0]))

    sections = []
    for continent, icon in CONTINENTS:
        entries = sorted(by_continent.get(continent, []), key=lambda e: e[1].lower())
        if not entries:
            continue
        cards = "\n".join(build_country_card(c, n) for c, n in entries)
        sections.append(
            f"""
        <section class="continent-section mb-12" data-continent="{continent.lower()}">
          <div class="flex items-center gap-3 mb-5">
            <span class="flex h-10 w-10 items-center justify-center rounded-lg
                         bg-blue-50 text-blue-600">
              <i class="fa-solid {icon}"></i>
            </span>
            <h2 class="text-xl font-bold text-slate-800">{continent}</h2>
            <span class="text-sm text-slate-400 font-medium">
              {len(entries)} {('country' if len(entries) == 1 else 'countries')}
            </span>
          </div>
          <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {cards}
          </div>
        </section>"""
        )

    all_files = [
        f"{c.lower()}_{fc}.geojson"
        for c in countries
        for fc, *_ in LAYERS
    ]

    page = PAGE_TEMPLATE
    page = page.replace("{{GENERATED_DATE}}", today)
    page = page.replace("{{COUNTRY_COUNT}}", str(len(countries)))
    page = page.replace("{{FILE_COUNT}}", str(len(all_files)))
    page = page.replace("{{SECTIONS}}", "\n".join(sections))
    page = page.replace("{{EXPECTED_FILES}}", __import__("json").dumps(all_files))
    page = page.replace("{{HF_API_TREE}}", HF_API_TREE)
    return page


def generate_geojsons_page() -> None:
    output = Path(__file__).with_name("web") / "geojsons.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_page(), encoding="utf-8")
    print(f"Wrote {output} ({output.stat().st_size / 1024:.0f} KB)")


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GeoJSON Downloads &middot; OpenAIP PMTile Generator</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link
      rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
    />
    <style>
      body {
        background-color: #f8fafc;
        font-family: "Inter", system-ui, -apple-system, sans-serif;
      }
      .card {
        background: white;
        border-radius: 12px;
        box-shadow:
          0 4px 6px -1px rgb(0 0 0 / 0.1),
          0 2px 4px -2px rgb(0 0 0 / 0.1);
      }
      .country-card {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
      }
      .country-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px -6px rgb(0 0 0 / 0.12);
      }
    </style>
  </head>
  <body class="flex flex-col min-h-screen">
    <!-- Header -->
    <header class="bg-slate-900 text-white">
      <nav class="container mx-auto px-4 py-4 flex items-center justify-between">
        <a href="index.html" class="flex items-center gap-2 font-semibold">
          <i class="fa-solid fa-plane-departure text-blue-400"></i>
          <span>OpenAIP PMTile Generator</span>
        </a>
        <div class="flex items-center gap-6 text-sm">
          <a href="index.html" class="text-slate-300 hover:text-white transition">
            Home
          </a>
          <a
            href="geojsons.html"
            class="text-white font-semibold border-b-2 border-blue-400 pb-0.5"
          >
            GeoJSON Downloads
          </a>
        </div>
      </nav>
      <div class="container mx-auto px-4 py-12 text-center">
        <i class="fa-solid fa-file-arrow-down text-4xl mb-4 text-blue-400"></i>
        <h1 class="text-3xl font-bold tracking-tight">Country GeoJSON Downloads</h1>
        <p class="mt-2 text-slate-400 max-w-2xl mx-auto">
          Raw OpenAIP <span class="text-white font-medium">airport</span> and
          <span class="text-white font-medium">airspace</span> datasets for every
          supported country, available individually.
        </p>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-grow container mx-auto px-4 py-10 max-w-6xl">
      <!-- Search + Stats -->
      <section class="card p-6 mb-10">
        <div class="relative">
          <i
            class="fa-solid fa-magnifying-glass absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
          ></i>
          <input
            id="search"
            type="text"
            autocomplete="off"
            placeholder="Search country or code&hellip; e.g. Slovakia, SK"
            class="w-full rounded-full border border-slate-200 bg-slate-50 pl-11 pr-11
                   py-3 text-slate-800 placeholder-slate-400 focus:outline-none
                   focus:ring-2 focus:ring-blue-400 focus:border-transparent"
          />
          <button
            id="clear-search"
            type="button"
            title="Clear search"
            class="hidden absolute right-3 top-1/2 -translate-y-1/2 h-7 w-7 items-center
                   justify-center rounded-full text-slate-400 hover:bg-slate-200
                   hover:text-slate-600 transition"
          >
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>

        <div class="mt-5 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="rounded-lg bg-slate-50 border border-slate-100 p-3 text-center">
            <div class="text-2xl font-bold text-slate-800">{{COUNTRY_COUNT}}</div>
            <div class="text-xs text-slate-500 font-medium mt-0.5">Countries</div>
          </div>
          <div class="rounded-lg bg-slate-50 border border-slate-100 p-3 text-center">
            <div class="text-2xl font-bold text-slate-800">{{FILE_COUNT}}</div>
            <div class="text-xs text-slate-500 font-medium mt-0.5">Downloadable files</div>
          </div>
          <div class="rounded-lg bg-slate-50 border border-slate-100 p-3 text-center">
            <div class="text-2xl font-bold text-slate-800" id="files-available">&ndash;</div>
            <div class="text-xs text-slate-500 font-medium mt-0.5">Available now</div>
          </div>
          <div class="rounded-lg bg-slate-50 border border-slate-100 p-3 text-center">
            <div class="text-2xl font-bold text-slate-800" id="total-size">&ndash;</div>
            <div class="text-xs text-slate-500 font-medium mt-0.5">Total size</div>
          </div>
        </div>

        <p class="mt-4 text-xs text-slate-400 italic">
          * File sizes are read live from the Hugging Face repository. Data is
          regenerated automatically once a week (Sundays 04:00 UTC) &mdash;
          last generated {{GENERATED_DATE}}.
        </p>
      </section>

      <noscript>
        <div class="card p-4 mb-8 text-sm text-amber-700 bg-amber-50 border border-amber-200">
          JavaScript is disabled &mdash; the search box and live file sizes won't work,
          but all download links remain available below.
        </div>
      </noscript>

      <!-- Continent sections -->
      {{SECTIONS}}
    </main>

    <!-- Footer -->
    <footer class="bg-slate-100 py-8 border-t border-slate-200">
      <div class="container mx-auto px-4 text-center text-slate-500 text-sm">
        <p>
          &copy; 2026 OpenAIP Community. All data provided as-is for
          informational purposes only. &middot;
          <a
            href="index.html"
            class="text-blue-600 hover:underline"
          >
            Back to home
          </a>
        </p>
      </div>
    </footer>

    <script>
      // Files we expect to exist (generated from countries.py).
      const EXPECTED = {{EXPECTED_FILES}};
      const HF_TREE_URL = "{{HF_API_TREE}}";

      function fmtSize(n) {
        if (n == null || isNaN(n)) return "\u2013";
        if (n < 1024) return n + " B";
        const units = ["KB", "MB", "GB"];
        let i = -1;
        do { n /= 1024; i += 1; } while (n >= 1024 && i < units.length - 1);
        return n.toFixed(1) + " " + units[i];
      }

      // Enrich the static list with live file sizes from Hugging Face.
      fetch(HF_TREE_URL)
        .then((res) => {
          if (!res.ok) throw new Error("tree unavailable");
          return res.json();
        })
        .then((items) => {
          const sizes = new Map();
          items.forEach((f) => {
            if (f && f.size != null) sizes.set(f.path.split("/").pop(), f.size);
          });

          let total = 0;
          let present = 0;
          document.querySelectorAll(".file-size").forEach((el) => {
            const size = sizes.get(el.dataset.file);
            if (size != null) {
              el.textContent = fmtSize(size);
              el.classList.remove("text-slate-400");
              el.classList.add("text-emerald-600");
              total += size;
              present += 1;
            } else {
              el.textContent = "pending";
              el.classList.add("text-slate-300");
            }
          });
          document.getElementById("files-available").textContent =
            present + " / " + EXPECTED.length;
          document.getElementById("total-size").textContent = fmtSize(total);
        })
        .catch(() => {
          // Keep the static links working even if the API is unreachable.
        });

      // Search filter across countries and continents.
      const searchInput = document.getElementById("search");
      const clearBtn = document.getElementById("clear-search");

      function applyFilter() {
        const q = searchInput.value.trim().toLowerCase();
        clearBtn.classList.toggle("hidden", q === "");
        document.querySelectorAll(".country-card").forEach((card) => {
          const match =
            q === "" ||
            card.dataset.name.includes(q) ||
            card.dataset.code.includes(q);
          card.style.display = match ? "" : "none";
        });
        document.querySelectorAll(".continent-section").forEach((sec) => {
          const visible = Array.from(
            sec.querySelectorAll(".country-card")
          ).some((c) => c.style.display !== "none");
          sec.style.display = visible ? "" : "none";
        });
      }

      searchInput.addEventListener("input", applyFilter);
      clearBtn.addEventListener("click", () => {
        searchInput.value = "";
        applyFilter();
        searchInput.focus();
      });
    </script>
  </body>
</html>
"""


if __name__ == "__main__":
    generate_geojsons_page()
