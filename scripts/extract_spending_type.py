"""Government spending by economic type (what the money is spent on, rather than what for), % of GDP.

Source: OECD Table 12, general government (S13) expenditure transactions, national currency.
Types (they add up exactly to total government spending, OTE):
  pay   D1   compensation of employees (wages and employers' social contributions)
  pur   P2   intermediate consumption: goods and services bought to run public services
  kind  D632 social transfers in kind bought from market producers (e.g. reimbursed medicines, private care)
  cash  D62  cash social benefits (pensions, unemployment, family, housing, assistance)
  inv   P5L  gross capital formation and land / non-produced assets (public investment)
  int   D41  interest on public debt
  sub   D3   subsidies to producers
  oth   the remainder of OTE: other current transfers (D7, incl. EU contributions), capital transfers (D9), taxes paid,
        other property income, pension adjustments

Usage (from the repository root):
  python3 scripts/extract_spending_type.py data/raw/DF_TABLE12.csv data/raw/GDP_USD.csv data/processed/spending_by_type.csv
"""
import csv, sys, collections

src, gdpf, out = sys.argv[1:]
gdp = {}
for r in csv.DictReader(open(gdpf, encoding="utf-8-sig")):
    if r["UNIT_MEASURE"] == "XDC" and r["OBS_VALUE"]: gdp[(r["REF_AREA"], r["TIME_PERIOD"])] = float(r["OBS_VALUE"])
CODES = {"OTE", "D1", "P2", "D632", "D62", "P5L", "D41", "D3"}
v = collections.defaultdict(dict)
with open(src, encoding="utf-8-sig", newline="") as fh:
    for r in csv.DictReader(fh):
        if (r["SECTOR"] == "S13" and r["ACCOUNTING_ENTRY"] in ("D", "_Z") and r["TRANSACTION"] in CODES
                and r["UNIT_MEASURE"] == "XDC" and r["OBS_VALUE"]):
            v[(r["REF_AREA"], r["TIME_PERIOD"])][r["TRANSACTION"]] = float(r["OBS_VALUE"])
rows = []
for (c, y), d in sorted(v.items()):
    g = gdp.get((c, y))
    if not g or "OTE" not in d or not all(k in d for k in ("D1", "P2", "D62", "P5L", "D41", "D3")): continue
    t = {"pay": d["D1"], "pur": d["P2"], "kind": d.get("D632", 0.0), "cash": d["D62"], "inv": d["P5L"], "int": d["D41"], "sub": d["D3"]}
    t["oth"] = max(0.0, d["OTE"] - sum(t.values()))
    rows.append([c, y] + [round(t[k] / g * 100, 4) for k in ("pay", "pur", "kind", "cash", "inv", "int", "sub", "oth")])
w = csv.writer(open(out, "w", newline=""))
w.writerow(["REF_AREA", "YEAR", "pay", "pur", "kind", "cash", "inv", "int", "sub", "oth"]); w.writerows(rows)
print(len(rows), "country-years;", len({r[0] for r in rows}), "countries")
