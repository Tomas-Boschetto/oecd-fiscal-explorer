"""Build the explorer's dataset and dashboard.

Reads
  data/raw/DF_NAAG_VI.csv                      OECD National Accounts at a Glance, ch. 6 (revenue, spending,
                                               balance, COFOG level 1, revenue groups; % of GDP)
  data/raw/GDP_USD.csv                         OECD Table 1 GDP (US$ PPP, US$ exchange rates, national currency)
  data/processed/cofog_level2.csv              COFOG level 2, all functions (extract_cofog_level2.py)
  data/processed/cofog_labels.json             COFOG code labels (extract_cofog_level2.py)
  data/processed/us_cofog_shares.json          US subcategory shares from BEA + CMS (us_subcategories.py)
  data/processed/revenue_detail.csv            revenue detail from OECD Table 12 (extract_revenue_detail.py)
  data/processed/revstats_income_tax_split.csv OECD Revenue Statistics 1100/1200/1300 (download_sources.py)
  data/processed/revstats_consumption_taxes.csv OECD Revenue Statistics 5111-5123 (download_sources.py)
  data/processed/argentina.json                Argentina from IMF, Argentine Ministry of Economy, SIPRI, OECD LAC (argentina.py)
  data/processed/debt.json                     government, household and corporate debt, IMF Global Debt Database (debt.py)
  src/template.html                            the dashboard, with a __DATA__ placeholder

Writes
  data/explorer_data.json    compact data embedded in the dashboard
  data/explorer_dataset.csv  the same data in long ("tidy") format, one value per row
  index.html                 the dashboard (a single self-contained file)

Run from the repository root:  python3 scripts/build_data.py
"""
import csv, json, collections, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, PROC = f"{ROOT}/data/raw", f"{ROOT}/data/processed"

# ---------- totals, COFOG level 1, revenue groups (% of GDP) ----------
names = {}; V = collections.defaultdict(dict)
want = {("OTRS13", "_Z"): "rev", ("OTES13", "_T"): "exp", ("B9S13", "_Z"): "bal", ("ODAS13_D2", "_Z"): "r_prod",
        ("ODAS13_D5", "_Z"): "r_inc", ("ODAS13_D91", "_Z"): "r_cap", ("D61S13", "_Z"): "r_soc", ("OTES13F", "_T"): "f_tot",
        ("LES13_FD4", "_Z"): "debt"}
for i in range(1, 11): want[("OTES13F", f"GF{i:02d}")] = f"f{i:02d}"
for r in csv.DictReader(open(f"{RAW}/DF_NAAG_VI.csv", encoding="utf-8-sig")):
    k = want.get((r["MEASURE"], r["EXPENDITURE"]))
    if k and r["UNIT_MEASURE"] == "PT_B1GQ" and r["OBS_VALUE"]:
        names[r["REF_AREA"]] = r["Reference area"]
        V[(r["REF_AREA"], int(r["TIME_PERIOD"]))][k] = round(float(r["OBS_VALUE"]), 3)

# ---------- GDP ----------
GDPX = {}
for r in csv.DictReader(open(f"{RAW}/GDP_USD.csv", encoding="utf-8-sig")):
    if not r["OBS_VALUE"]: continue
    key = (r["REF_AREA"], int(r["TIME_PERIOD"]))
    if r["UNIT_MEASURE"] == "XDC": GDPX[key] = float(r["OBS_VALUE"]) * 10 ** int(r["UNIT_MULT"] or 6)
    elif r["UNIT_MEASURE"] in ("USD_PPP", "USD_EXC") and key in V:   # millions -> billions
        V[key]["gdp_" + ("ppp" if r["UNIT_MEASURE"] == "USD_PPP" else "exc")] = round(float(r["OBS_VALUE"]) / 1000, 2)

# ---------- COFOG level 2 (% of GDP), stored per row as l2 = {"0703": 3.1, ...} ----------
for r in csv.DictReader(open(f"{PROC}/cofog_level2.csv")):
    key = (r["REF_AREA"], int(r["YEAR"]))
    if key in V and key[1] >= 1995 and r["PCT_GDP"] and len(r["COFOG"]) == 6:
        V[key].setdefault("l2", {})[r["COFOG"][2:]] = round(float(r["PCT_GDP"]), 3)
# United States: no level 2 in OECD data. Split each OECD function total using BEA / CMS shares (estimate).
us = json.load(open(f"{PROC}/us_cofog_shares.json"))
for (c, y), v in V.items():
    if c != "USA" or y < 1995 or str(y) not in us: continue
    est = []
    for fn, parts in us[str(y)].items():
        tot = v.get("f" + fn[2:])
        if tot is None: continue
        for code, share in parts.items(): v.setdefault("l2", {})[code[2:]] = round(share * tot, 3)
        est.append(fn[2:])
    if est: v["est"] = est
labels = {k[2:]: l for k, l in json.load(open(f"{PROC}/cofog_labels.json")).items()}

# ---------- revenue detail (% of GDP) -> row "rd" ----------
RD = collections.defaultdict(dict)
for r in csv.DictReader(open(f"{PROC}/revenue_detail.csv")): RD[(r["REF_AREA"], int(r["YEAR"]))][r["TRANSACTION"]] = float(r["PCT_GDP"])
RS = collections.defaultdict(dict)
for r in csv.DictReader(open(f"{PROC}/revstats_income_tax_split.csv")): RS[(r["REF_AREA"], int(r["YEAR"]))][r["CODE"]] = float(r["VALUE_XDC"])
SALES = collections.defaultdict(float)   # Revenue Statistics 5112 sales taxes + 5113 other general taxes, national currency
for r in csv.DictReader(open(f"{PROC}/revstats_consumption_taxes.csv")):
    if r["CODE"] in ("T_5112", "T_5113"): SALES[(r["REF_AREA"], int(r["YEAR"]))] += float(r["VALUE_XDC"]) * 10 ** int(r["UNIT_MULT"])
def sales_pct(key):
    """Sales taxes in % of GDP. Revenue Statistics lags by a year or two: carry the latest ratio forward (max 2 years)."""
    for k in (0, 1, 2):
        kk = (key[0], key[1] - k)
        if kk in SALES and kk in GDPX: return SALES[kk] / GDPX[kk] * 100
    return 0.0
n_rd = n_est = 0
for key, v in V.items():
    d = RD.get(key)
    if not d or key[1] < 1995: continue
    g = d.get; rd = {}
    if g("D21") is not None and g("D29") is not None:
        vat = g("D211") or 0.0
        sales = min(sales_pct(key), max(0, g("D21") - vat))  # national accounts book sales taxes with excise duties
        rd.update(gct=vat + sales, otp=max(0, g("D21") - vat - sales), opr=g("D29"))
        if sales > 0.2: v["prd_est"] = 1                      # flag only where sales taxes are material
    if g("D611") is not None and g("D613") is not None:
        rd.update(sce=g("D611"), sch=g("D613"), sci=g("D612_D614") or 0.0)
    if g("D4") is not None and g("P1O") is not None:
        d41 = g("D41") or 0.0
        rd.update(sal=g("P1O"), int=d41, pin=max(0, g("D4") - d41), trf=(g("D7") or 0.0) + (g("D39") or 0.0),
                  cpt=g("D91") or 0.0, kot=max(0, (g("D9") or 0.0) - (g("D91") or 0.0)))
    d5 = g("D5")
    if d5 is not None:
        # Some countries (e.g. Colombia, New Zealand) report D51M and D51O as 0 when they don't split them: treat as missing
        if g("D51M") is not None and g("D51O") is not None and g("D51M") + g("D51O") > 0.05 * (g("D51") or d5):
            rd.update(pit=g("D51M"), cit=g("D51O"), oti=max(0, d5 - g("D51M") - g("D51O")))
        else:
            s = RS.get(key, {}); tot = sum(s.get(c, 0) for c in ("T_1100", "T_1200", "T_1300"))
            if tot > 0:
                base = g("D51") if g("D51") is not None else d5
                rd.update(pit=base * s.get("T_1100", 0) / tot, cit=base * s.get("T_1200", 0) / tot,
                          oti=max(0, d5 - base * (s.get("T_1100", 0) + s.get("T_1200", 0)) / tot))
                v["inc_est"] = 1; n_est += 1
    if rd: v["rd"] = {k: round(x, 3) for k, x in rd.items()}; n_rd += 1

# ---------- Argentina (not in OECD national accounts; built by argentina.py from other sources) ----------
arg_path = f"{PROC}/argentina.json"
if os.path.exists(arg_path):
    names["ARG"] = "Argentina"
    for y, v in json.load(open(arg_path)).items():
        if int(y) >= 1995: V[("ARG", int(y))] = v

# ---------- debt by sector (% of GDP) ----------
debt_path = f"{PROC}/debt.json"
if os.path.exists(debt_path):
    for c, years in json.load(open(debt_path)).items():
        for y, d in years.items():
            v = V.get((c, int(y)))
            if v is None: continue
            for k in ("gov", "hh", "nfc"):
                if k in d: v["d_" + k] = d[k]
            if d.get("gov_weo"): v["d_est"] = 1

# ---------- outputs ----------
rows = [{"c": a, "y": y, **v} for (a, y), v in sorted(V.items()) if "rev" in v or "exp" in v]
out = {"names": names, "labels": labels, "rows": rows}
os.makedirs(f"{ROOT}/data", exist_ok=True)
json.dump(out, open(f"{ROOT}/data/explorer_data.json", "w"), separators=(",", ":"))
t = open(f"{ROOT}/src/template.html", encoding="utf-8").read()
open(f"{ROOT}/index.html", "w", encoding="utf-8").write(t.replace("__DATA__", json.dumps(out, separators=(",", ":"))))

# Long-format CSV: one value per row, every value in % of GDP unless stated
FN = {"01": "General public services", "02": "Defence", "03": "Public order and safety", "04": "Economic affairs",
      "05": "Environmental protection", "06": "Housing and community amenities", "07": "Health",
      "08": "Recreation, culture and religion", "09": "Education", "10": "Social protection"}
RDN = {"pit": ("income", "Personal income taxes"), "cit": ("income", "Corporate income taxes"), "oti": ("income", "Other taxes on income and wealth"),
       "gct": ("production", "General consumption taxes (VAT and sales taxes)"), "otp": ("production", "Excise, customs and other taxes on products"),
       "opr": ("production", "Other taxes on production"), "sce": ("social_contributions", "Employers' contributions"),
       "sch": ("social_contributions", "Employees' and self-employed contributions"), "sci": ("social_contributions", "Imputed contributions"),
       "sal": ("other", "Sales of goods and services, fees"), "int": ("other", "Interest received"), "pin": ("other", "Other property income"),
       "trf": ("other", "Transfers received"), "cpt": ("other", "Capital taxes"), "kot": ("other", "Other capital transfers")}
SRC_RS = "OECD National Accounts + OECD Revenue Statistics"
with open(f"{ROOT}/data/explorer_dataset.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["country_code", "country", "year", "group", "code", "name", "level", "value", "unit", "estimated", "source"])
    for r in rows:
        c, y, nm = r["c"], r["y"], names.get(r["c"], r["c"])
        alt = bool(r.get("alt"))   # Argentina: every value comes from non-OECD sources
        SRC_NA = "IMF Fiscal Monitor; Argentina Ministry of Economy; SIPRI; OECD Revenue Statistics LAC" if alt else "OECD National Accounts"
        def put(group, code, name, level, val, unit="pct_gdp", est=False, src=SRC_NA):
            if val is not None: w.writerow([c, nm, y, group, code, name, level, val, unit, int(est or alt), SRC_NA if alt else src])
        put("total", "revenue", "Total revenue", 0, r.get("rev"))
        put("total", "spending", "Total spending", 0, r.get("exp"))
        put("total", "balance", "Net lending (+) / borrowing (-)", 0, r.get("bal"))
        put("total", "gross_debt", "Gross debt", 0, r.get("debt"))
        put("gdp", "gdp_usd_ppp", "GDP, US$ PPP", 0, r.get("gdp_ppp"), "usd_bn")
        put("gdp", "gdp_usd_exc", "GDP, US$ exchange rates", 0, r.get("gdp_exc"), "usd_bn")
        for fn, fname in FN.items(): put("spending", fn, fname, 1, r.get("f" + fn))
        DSRC = "IMF Global Debt Database"
        put("debt", "government", "Government debt", 1, r.get("d_gov"), est=bool(r.get("d_est")),
            src="IMF World Economic Outlook" if r.get("d_est") else DSRC)
        put("debt", "households", "Household debt", 1, r.get("d_hh"), src=DSRC)
        put("debt", "companies", "Non-financial corporate debt", 1, r.get("d_nfc"), src=DSRC)
        for code, val in sorted((r.get("l2") or {}).items()):
            est = code[:2] in r.get("est", [])
            put("spending", code, labels.get(code, code), 2, val, est=est, src="US: BEA / CMS shares x OECD total" if est else SRC_NA)
        for k, name in (("r_inc", "Taxes on income and wealth"), ("r_prod", "Taxes on production and imports"), ("r_soc", "Social contributions")):
            put("revenue", k[2:], name, 1, r.get(k))
        for k, val in (r.get("rd") or {}).items():
            grp, name = RDN[k]
            est = (grp == "income" and r.get("inc_est")) or (grp == "production" and k in ("gct", "otp") and r.get("prd_est"))
            put("revenue", f"{grp}.{k}", name, 2, val, est=bool(est), src=SRC_RS if est else SRC_NA)

print(f"{len(rows)} country-years; {sum('l2' in r for r in rows)} with spending subcategories; "
      f"{n_rd} with revenue detail ({n_est} income-tax splits from Revenue Statistics); "
      f"index.html {round(os.path.getsize(f'{ROOT}/index.html') / 1e6, 2)} MB")
