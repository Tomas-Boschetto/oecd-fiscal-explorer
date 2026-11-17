"""Large non-OECD G20 economies: China, India, Brazil, Indonesia, Saudi Arabia, South Africa.

None of them is in the OECD national-accounts tables the explorer uses (Brazil and Indonesia only partly), so their
figures are built from other public sources, like Argentina's (see argentina.py):

  Totals (revenue, spending, balance, gross debt), GDP in US$:
      IMF Fiscal Monitor / World Economic Outlook (DataMapper API), general government, up to 2024.
  Spending by function (COFOG):
      IMF Government Finance Statistics, dataset GFS_COFOG, general government (sector S13), % of GDP.
      Available for Brazil, South Africa, China and, at the main-category level, Indonesia. India and Saudi Arabia
      publish no general-government breakdown by function, so they have totals only. The IMF split is applied to the
      IMF Fiscal Monitor spending total (the explorer scales it). Subcategories are kept only for categories where
      they add up to at least 90% of the category total.
  Tax revenue by type:
      OECD Global Revenue Statistics (DF_RSGLOBAL), % of GDP, for Brazil, China, Indonesia and South Africa,
      mapped to the national-accounts groups the same way as for Argentina.

Writes data/raw/partners/* (downloads) and data/processed/partners.json: {country: {year: row}}, with the same
field names as the rows in data/explorer_data.json.

Usage (from the repository root):
  python3 scripts/partners.py             # download and build
  python3 scripts/partners.py --offline   # rebuild from the files already in data/raw/partners
"""
import csv, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, OUT = f"{ROOT}/data/raw/partners", f"{ROOT}/data/processed/partners.json"
UA = {"User-Agent": "public-finance-explorer/1.0 (+https://github.com/Tomas-Boschetto/public-finance-explorer)"}
COUNTRIES = {"CHN": "China", "IND": "India", "BRA": "Brazil", "IDN": "Indonesia", "SAU": "Saudi Arabia", "ZAF": "South Africa"}
FIRST, LAST_ACTUAL = 1995, 2024
IMF_SERIES = ("GGR_G01_GDP_PT", "G_X_G01_GDP_PT", "GGXCNL_G01_GDP_PT", "G_XWDG_G01_GDP_PT", "NGDPD", "PPPGDP")
KEY = "+".join(COUNTRIES)

def fetch(url, accept=None):
    h = dict(UA)
    if accept: h["Accept"] = accept
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=900) as r: return r.read()

def download():
    os.makedirs(RAW, exist_ok=True)
    jobs = {f"imf_{s}.json": (f"https://www.imf.org/external/datamapper/api/v1/{s}", None) for s in IMF_SERIES}
    jobs["imf_gfs_cofog.csv"] = (f"https://api.imf.org/external/sdmx/2.1/data/IMF.STA,GFS_COFOG/{KEY}.S13.G2MF..POGDP_PT.A?startPeriod={FIRST}",
                                 "application/vnd.sdmx.data+csv;version=1.0.0")
    jobs["oecd_revstats_global.csv"] = (f"https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_REV_COMP_GLOBAL@DF_RSGLOBAL,/{KEY}.TAX_REV.S13.._T.PT_B1GQ.A?format=csvfilewithlabels", None)
    for name, (url, acc) in jobs.items():
        print(f"  {name} ...", end=" ", flush=True); data = fetch(url, acc)
        if name == "imf_gfs_cofog.csv":   # keep only the columns used, the full file is ~80 MB of metadata
            rows = csv.DictReader(data.decode("utf-8-sig").splitlines())
            keep = ["COUNTRY", "SECTOR", "INDICATOR", "TIME_PERIOD", "OBS_VALUE"]
            with open(f"{RAW}/{name}", "w", newline="") as fh:
                w = csv.writer(fh); w.writerow(keep)
                for r in rows:
                    if r["OBS_VALUE"]: w.writerow([r[k] for k in keep])
            print("done")
        else:
            open(f"{RAW}/{name}", "wb").write(data); print(f"{len(data) / 1e3:.0f} kB")

def imf(series):
    v = json.load(open(f"{RAW}/imf_{series}.json"))["values"]
    return v[next(iter(v))]

def cofog_code(ind):
    """IMF indicator -> explorer code. GF07_T -> '07' (level 1); GF011_T / GF0140_T / GF1020_T -> '0101' / '0104' / '1002'."""
    c = ind[2:-2]
    return c if len(c) == 2 else c[:2] + "0" + c[2]

def tax_rd(t):
    """OECD Revenue Statistics codes (% of GDP) -> explorer revenue detail (same mapping as argentina.py)."""
    T = lambda *codes: sum(t.get(c, 0.0) for c in codes)
    return dict(pit=T("1100"), cit=T("1200"), oti=T("1300", "4200", "4110"),
                gct=T("5110"), otp=T("5120", "5130", "5300", "4400"), opr=T("5200", "4120", "3000", "6000", "4500", "4600"),
                sce=T("2200"), sch=T("2100", "2300", "2400"), sci=0.0)

def build():
    S = {s: imf(s) for s in IMF_SERIES}
    gfs = {}
    for r in csv.DictReader(open(f"{RAW}/imf_gfs_cofog.csv")):
        if r["SECTOR"] == "S13" and r["INDICATOR"].startswith("GF"):
            gfs.setdefault(r["COUNTRY"], {}).setdefault(int(r["TIME_PERIOD"][:4]), {})[cofog_code(r["INDICATOR"])] = float(r["OBS_VALUE"])
    tax = {}
    for r in csv.DictReader(open(f"{RAW}/oecd_revstats_global.csv", encoding="utf-8-sig")):
        if r["OBS_VALUE"]: tax.setdefault(r["REF_AREA"], {}).setdefault(int(r["TIME_PERIOD"]), {})[r["STANDARD_REVENUE"][2:]] = float(r["OBS_VALUE"])
    out, summary = {}, []
    for c in COUNTRIES:
        rev, exp, bal, debt = (S[s].get(c, {}) for s in ("GGR_G01_GDP_PT", "G_X_G01_GDP_PT", "GGXCNL_G01_GDP_PT", "G_XWDG_G01_GDP_PT"))
        years = {}
        for y in range(FIRST, LAST_ACTUAL + 1):
            ys = str(y)
            if ys not in rev or ys not in exp: continue
            v = {"rev": round(rev[ys], 3), "exp": round(exp[ys], 3), "bal": round(bal.get(ys, rev[ys] - exp[ys]), 3), "alt": 1}
            if ys in debt: v["debt"] = round(debt[ys], 3)
            for s, k in (("NGDPD", "gdp_exc"), ("PPPGDP", "gdp_ppp")):
                if ys in S[s].get(c, {}): v[k] = round(S[s][c][ys], 2)
            g = gfs.get(c, {}).get(y)
            if g and all(f"{i:02d}" in g for i in range(1, 11)):
                for i in range(1, 11): v[f"f{i:02d}"] = round(g[f"{i:02d}"], 3)
                l2 = {}
                for i in range(1, 11):
                    fn = f"{i:02d}"; parts = {k: x for k, x in g.items() if len(k) == 4 and k[:2] == fn}
                    if parts and g[fn] > 0 and sum(parts.values()) >= 0.9 * g[fn]: l2.update(parts)
                if l2: v["l2"] = {k: round(x, 3) for k, x in l2.items()}; v["est"] = sorted({k[:2] for k in l2})
            t = tax.get(c, {}).get(y)
            if t and "1100" in t:
                rd = tax_rd(t)
                v["r_inc"] = round(rd["pit"] + rd["cit"] + rd["oti"], 3)
                v["r_prod"] = round(rd["gct"] + rd["otp"] + rd["opr"], 3)
                v["r_soc"] = round(rd["sce"] + rd["sch"], 3)
                v["r_cap"] = round(t.get("4300", 0.0), 3)
                v["rd"] = {k: round(x, 3) for k, x in rd.items()}
                v["inc_est"] = 1; v["prd_est"] = 1
            years[ys] = v
        out[c] = years
        fy = [y for y, v in years.items() if "f07" in v]
        summary.append(f"{c}: {min(years)}-{max(years)}, functions {min(fy) + '-' + max(fy) if fy else 'none'}, "
                       f"taxes {'yes' if any('rd' in v for v in years.values()) else 'no'}")
    json.dump({"names": COUNTRIES, "data": out}, open(OUT, "w"), separators=(",", ":"))
    print("\n".join(summary))

if __name__ == "__main__":
    if "--offline" not in sys.argv: download()
    build()
