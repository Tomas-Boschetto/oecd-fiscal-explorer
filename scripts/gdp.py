"""GDP structure: by industry (value added) and by use (expenditure), in % of GDP.

Sources (OECD National Accounts, current prices, national currency):
  DF_TABLE6               value added (B1G) by economic activity, ISIC Rev. 4, down to about 60 industries
  DF_TABLE1_EXPENDITURE   GDP (B1GQ), final consumption of households and NPISHs (P3, S1M), of government (P3, S13),
                          gross fixed capital formation (P51G), exports (P6), imports (P7)

By industry: 8 groups of ISIC sections, each split into industries (see TREE). Value added adds up to "gross value
added", which is GDP minus taxes less subsidies on products, so the groups add up to roughly 85-95% of GDP.
By use: household consumption, government consumption, investment, inventories (computed as the remainder, so it also
holds the statistical discrepancy) and net exports. They add up to 100% of GDP.

Writes data/raw/gdp/* (downloads) and data/processed/gdp_structure.json.

Usage (from the repository root):
  python3 scripts/gdp.py             # download (about 65 MB) and build
  python3 scripts/gdp.py --offline   # rebuild from the files already in data/raw/gdp
"""
import csv, json, os, sys, urllib.request, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, OUT = f"{ROOT}/data/raw/gdp", f"{ROOT}/data/processed/gdp_structure.json"
UA = {"User-Agent": "public-finance-explorer/1.0 (+https://github.com/Tomas-Boschetto/public-finance-explorer)"}
B = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.NAD,DSD_NAMAIN10"
FILES = {"oecd_value_added_by_activity.csv": f"{B}@DF_TABLE6,/A....B1G....XDC.V..?format=csvfilewithlabels&startPeriod=1995",
         "oecd_gdp_expenditure.csv": f"{B}@DF_TABLE1_EXPENDITURE,/A....P3+P31+P51G+P52_P53+P6+P7+B1GQ....XDC.V..?format=csvfilewithlabels&startPeriod=1995"}

# Industry tree: group -> (name, ISIC sections, [(sub key, name, alternatives)]). Each alternative is a list of ISIC
# codes whose sum gives the sub-industry; the first alternative the country reports in full is used.
TREE = [
  ("agr", "Agriculture, forestry and fishing", ["A"], [
      ("A01", "Crops and livestock", [["A01"]]), ("A02", "Forestry and logging", [["A02"]]), ("A03", "Fishing and aquaculture", [["A03"]])]),
  ("min", "Mining, energy and water", ["B", "D", "E"], [
      ("B", "Mining and quarrying (incl. oil and gas)", [["B"]]), ("D", "Electricity and gas supply", [["D"]]),
      ("E36", "Water supply", [["E36"]]), ("E37T39", "Sewerage and waste management", [["E37T39"]])]),
  ("man", "Manufacturing", ["C"], [
      ("C10T12", "Food, beverages and tobacco", [["C10T12"]]),
      ("C13T18", "Textiles, clothing, wood, paper and printing", [["C13T15", "C16T18"], ["C13T15", "C16", "C17", "C18"]]),
      ("C19T21", "Refined petroleum, chemicals and pharmaceuticals", [["C19", "C20", "C21"]]),
      ("C22_23", "Rubber, plastics, glass and cement", [["C22_23"], ["C22", "C23"]]),
      ("C24_25", "Metals and metal products", [["C24_25"], ["C24", "C25"]]),
      ("C26T28", "Electronics, electrical equipment and machinery", [["C26", "C27", "C28"]]),
      ("C29_30", "Cars and other transport equipment", [["C29_30"], ["C29", "C30"]]),
      ("C31T33", "Furniture, other manufacturing and repair", [["C31T33"], ["C31_32", "C33"]])]),
  ("con", "Construction", ["F"], [("F", "Construction", [["F"]])]),
  ("trd", "Trade, transport, hotels and restaurants", ["G", "H", "I"], [
      ("G45", "Car sales and repair", [["G45"]]), ("G46", "Wholesale trade", [["G46"]]), ("G47", "Retail trade", [["G47"]]),
      ("H49", "Land transport and pipelines", [["H49"]]), ("H50_51", "Water and air transport", [["H50", "H51"]]),
      ("H52_53", "Warehousing, logistics and postal services", [["H52", "H53"]]), ("I", "Hotels and restaurants", [["I"]])]),
  ("inf", "Information, finance and real estate", ["J", "K", "L"], [
      ("J58T60", "Publishing, film, TV and radio", [["J58T60"], ["J58", "J59_60"]]), ("J61", "Telecommunications", [["J61"]]),
      ("J62_63", "Software and IT services", [["J62_63"]]), ("K64", "Banking and other financial services", [["K64"]]),
      ("K65_66", "Insurance, pension funds and auxiliary finance", [["K65", "K66"]]),
      ("L68A", "Imputed rent of owner-occupied homes", [["L68A"]]), ("L68B", "Other real estate (rents, property services)", [["L-L68A"]])]),
  ("bus", "Professional and business services", ["M", "N"], [
      ("M69T71", "Legal, accounting, consulting, architecture and engineering", [["M69T71"], ["M69_70", "M71"]]),
      ("M72", "Scientific research and development", [["M72"]]), ("M73T75", "Advertising, design and other professional services", [["M73T75"], ["M73", "M74_75"]]),
      ("N77", "Rental and leasing", [["N77"]]), ("N78", "Employment agencies", [["N78"]]),
      ("N79T82", "Travel agencies, security, cleaning and office support", [["N79", "N80T82"]])]),
  ("pub", "Public administration, education, health and other services", ["O", "P", "Q", "R", "S", "T"], [
      ("O", "Public administration and defence", [["O"]]), ("P", "Education", [["P"]]), ("Q86", "Health care", [["Q86"]]),
      ("Q87_88", "Residential care and social work", [["Q87_88"]]), ("R", "Arts, entertainment and recreation", [["R"]]),
      ("S", "Other services (associations, repairs, personal services)", [["S"]]), ("T", "Households as employers", [["T"]])]),
]
USE = [("hh", "Household consumption"), ("gov", "Government consumption"), ("inv", "Investment (fixed capital)"),
       ("stk", "Inventories and statistical discrepancy"), ("nx", "Net exports (exports minus imports)")]

def download():
    os.makedirs(RAW, exist_ok=True)
    for name, url in FILES.items():
        print(f"  {name} ...", end=" ", flush=True)
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800).read()
        open(f"{RAW}/{name}", "wb").write(data); print(f"{len(data) / 1e6:.0f} MB")

def read(name):
    out = collections.defaultdict(dict)
    for r in csv.DictReader(open(f"{RAW}/{name}", encoding="utf-8-sig")):
        if r["OBS_VALUE"]:
            out[(r["REF_AREA"], int(r["TIME_PERIOD"]))][(r["TRANSACTION"], r["SECTOR"], r["ACTIVITY"])] = float(r["OBS_VALUE"]) * 10 ** int(r["UNIT_MULT"] or 0)
    return out

def build():
    va, ex = read("oecd_value_added_by_activity.csv"), read("oecd_gdp_expenditure.csv")
    out = {}
    for key in sorted(set(va) | set(ex)):
        e = {(k[0], k[1]): val for k, val in ex.get(key, {}).items()}   # activity code varies (_Z / _T); not needed here
        gdp = e.get(("B1GQ", "S1"))
        if not gdp: continue
        pct = lambda v: round(v / gdp * 100, 3)
        rec = {}
        # by use
        hh = e.get(("P3", "S1M")) or ((e.get(("P3", "S14")) or 0) + (e.get(("P3", "S15")) or 0)) or None
        gov, inv, x, m = e.get(("P3", "S13")), e.get(("P51G", "S1")), e.get(("P6", "S1")), e.get(("P7", "S1"))
        if hh is None and e.get(("P3", "S1")) is not None and gov is not None: hh = e[("P3", "S1")] - gov   # total consumption minus government
        if gov is None and e.get(("P3", "S1")) is not None and hh is not None: gov = e[("P3", "S1")] - hh   # total consumption minus households
        if None not in (hh, gov, inv, x, m):
            rec["use"] = {"hh": pct(hh), "gov": pct(gov), "inv": pct(inv), "stk": pct(gdp - hh - gov - inv - (x - m)),
                          "nx": pct(x - m), "exp": pct(x), "imp": pct(m)}
        # by industry
        v = {k[2]: val for k, val in va.get(key, {}).items() if k[0] == "B1G"}
        if "L" in v and "L68A" in v: v["L-L68A"] = v["L"] - v["L68A"]
        v.setdefault("T", 0.0)   # households as employers: tiny, and not reported by e.g. Japan, Korea, Australia
        # Some countries report a few sections only in combined form (e.g. Japan: E, N, S). Groups use the sections
        # available; the remainder of total value added is kept as "un" (not allocated) if at least 80% is allocated.
        tot = v.get("_T")
        alloc = sum(v.get(s, 0.0) for g in TREE for s in g[2])
        if tot and alloc >= 0.8 * tot:
            gi, gs = {}, {}
            missing = [s for g in TREE for s in g[2] if s not in v]
            for gk, _, secs, subs in TREE:
                gi[gk] = sum(v.get(s, 0.0) for s in secs)
                parts = {}
                for sk, _, alts in subs:
                    for alt in alts:
                        if all(c in v for c in alt): parts[sk] = sum(v[c] for c in alt); break
                if parts and sum(parts.values()) >= 0.9 * gi[gk]: gs.update({sk: pct(x) for sk, x in parts.items()})
            if tot - alloc > 0.005 * gdp: gi["un"] = tot - alloc
            rec["ind"] = {k: pct(x) for k, x in gi.items()}
            if missing: rec["ind_missing"] = missing
            if gs: rec["sub"] = gs
        if rec: out.setdefault(key[0], {})[str(key[1])] = rec
    tree = [{"k": gk, "name": nm, "sections": secs, "subs": [{"k": sk, "name": sn} for sk, sn, _ in subs]} for gk, nm, secs, subs in TREE]
    json.dump({"tree": tree, "use": [{"k": k, "name": n} for k, n in USE], "data": out}, open(OUT, "w"), separators=(",", ":"))
    ind = [c for c, ys in out.items() if any("ind" in r for r in ys.values())]
    use = [c for c, ys in out.items() if any("use" in r for r in ys.values())]
    print(f"GDP structure: by industry for {len(ind)} economies, by use for {len(use)}")
    for c in ("USA", "DEU", "CHN", "IND"):
        r = out.get(c, {}).get("2023", {})
        print(" ", c, "2023 industry:", r.get("ind"), "| use:", r.get("use"))

if __name__ == "__main__":
    if "--offline" not in sys.argv: download()
    build()
