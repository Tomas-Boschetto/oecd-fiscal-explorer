"""Estimates COFOG level-2 shares for the United States, which does not report them to the OECD.

Health (07.x): CMS National Health Expenditure Accounts, government-funded spending by type of service
  (Medicare, Medicaid, CHIP, DoD, VA, Indian Health, other public programs, public health, public research,
  public structures & equipment). Private insurance, out-of-pocket, other private revenues and workers'
  compensation are excluded.
Other functions: BEA NIPA Table 3.16, government current expenditures by function (federal + state and local).

The output holds SHARES of each function. The explorer multiplies them by the OECD function total, so the
US function totals stay exactly the OECD figures; only the split inside each function is estimated.
Usage (from the repository root):
  python3 scripts/us_subcategories.py data/raw data/processed/us_cofog_shares.json"""
import csv, json, sys, re, collections
src, out = sys.argv[1:]

# ---------- BEA Table 3.16 ----------
bea = collections.defaultdict(dict)
for r in csv.reader(open(f"{src}/NipaDataA.txt")):
    if len(r) >= 3 and r[0] != "%SeriesCode":
        try: bea[r[0]][int(r[1])] = float(r[2].replace(",", ""))
        except ValueError: pass
BEA_MAP = {  # COFOG level-2 code -> BEA series (total government)
    "GF0101": ["G16003", "G16004"],   # executive & legislative; tax collection & financial management
    "GF0107": ["G16005"],             # interest payments
    "GF0106": ["G16006"],             # other general public service
    "GF0301": ["G16009"], "GF0302": ["G16010"], "GF0303": ["G16011"], "GF0304": ["G16012"],
    "GF0401": ["G16014"],             # general economic and labor affairs
    "GF0402": ["G16015", "G16017"],   # agriculture; natural resources
    "GF0403": ["G16016"],             # energy
    "GF0405": ["G16018"],             # transportation
    "GF0406": ["G16023"],             # postal service
    "GF0409": ["G16024", "G16025"],   # space; other
    "GF0901": ["G16030"],             # elementary and secondary (US does not split primary / secondary)
    "GF0904": ["G16031"],             # higher education
    "GF0908": ["W691RC"],             # libraries and other
    "GF1001": ["G16035"], "GF1002": ["G16036"], "GF1005": ["G16038"],
    "GF1007": ["G16037"],             # welfare and social services
    "GF1009": ["G16039"],             # other income security
}

# ---------- CMS NHE by type of service and source of funds ----------
rows = list(csv.reader(open(f"{src}/cms/NHE.csv", encoding="latin-1")))
hdr = rows[1]; ycol = {int(h): i for i, h in enumerate(hdr) if h.strip().isdigit()}
def num(s):
    s = s.strip().replace(",", "")
    try: return float(s)
    except ValueError: return 0.0
PUBLIC = ["Medicare", "Medicaid (Title XIX)", "CHIP (Title XIX and Title XXI)", "Department of Defense",
          "Department of Veterans Affairs", "Indian Health Services", "General Assistance", "Maternal/Child Health",
          "Vocational Rehabilitation", "Other Federal Programs*", "SAMHSA", "Other State and Local Programs**", "School Health"]
BLOCKS = {  # CMS block title -> COFOG code
    "Total Hospital Expenditures": "GF0703",
    "Total Nursing Care Facilities and Continuing Care Retirement Communities": "GF0703",
    "Total Other Health, Residential, and Personal Care Expenditures": "GF0703",
    "Total Physician and Clinical Expenditures": "GF0702",
    "Total Dental Services Expenditures": "GF0702",
    "Total Other Professional Services Expenditures": "GF0702",
    "Total Home Health Care Expenditures": "GF0702",
    "Total Prescription Drug Expenditures": "GF0701",
    "Other Non-Durable Medical Products Expenditures": "GF0701",
    "Total Durable Medical Equipment Expenditures": "GF0701",
    "Total Administration and Total Non-Medical Insurance Expenditures": "GF0706",
}
health = collections.defaultdict(lambda: collections.defaultdict(float))
block = None
for i, r in enumerate(rows):
    if not r or not r[0]: continue
    name = r[0].strip()
    if not r[0].startswith(" "):  # a new block starts at an unindented title
        block = BLOCKS.get(name) or {"Public Health Activity": "PHA", "Research": "RES",
                                     "Total Structures and Equipment": "SE"}.get(name)
        continue
    if block is None: continue
    ind = len(r[0]) - len(r[0].lstrip())
    for y, c in ycol.items():
        v = num(r[c]) if c < len(r) else 0.0
        if block in BLOCKS.values() and name in PUBLIC: health[y][block] += v
        elif block == "PHA" and name in ("Federal Funds", "State/Local Funds"): health[y]["GF0704"] += v
        elif block == "RES" and name in ("Federal Gov't", "State and Local Gov't"): health[y]["GF0705"] += v
        elif block == "SE" and ind <= 5 and name in ("Federal Gov't", "State and Local Gov't"): health[y]["GF0706"] += v

# ---------- shares per function ----------
res = {}
years = sorted(set(y for s in BEA_MAP.values() for c in s for y in bea.get(c, {})) | set(health))
for y in years:
    sh = {}
    by_fn = collections.defaultdict(dict)
    for code, series in BEA_MAP.items():
        if all(y in bea.get(s, {}) for s in series):
            by_fn[code[:4]][code] = max(0.0, sum(bea[s][y] for s in series))
    if y in health: by_fn["GF07"] = {k: max(0.0, v) for k, v in health[y].items()}
    for fn, parts in by_fn.items():
        tot = sum(parts.values())
        if tot > 0: sh[fn] = {k: round(v / tot, 5) for k, v in parts.items()}
    if sh: res[y] = sh
json.dump(res, open(out, "w"), separators=(",", ":"))
y = 2023
print("years", min(res), "-", max(res))
for fn, parts in sorted(res[y].items()): print(y, fn, {k[-2:]: round(v * 100, 1) for k, v in sorted(parts.items(), key=lambda kv: -kv[1])})
