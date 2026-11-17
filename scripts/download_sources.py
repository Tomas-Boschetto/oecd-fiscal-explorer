"""Download the source data into data/raw (and the small Revenue Statistics extracts into data/processed).

  python3 scripts/download_sources.py          # quick: what build_data.py needs (about 35 MB)
  python3 scripts/download_sources.py --full   # also the large tables needed to re-extract subcategories
                                               # (OECD Table 11 is about 3.2 GB, Table 12 about 250 MB)

Only the Python standard library is used. Downloads are public and need no account or key.
"""
import csv, io, os, sys, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, PROC = f"{ROOT}/data/raw", f"{ROOT}/data/processed"
OECD = "https://sdmx.oecd.org/public/rest/data"
UA = {"User-Agent": "oecd-fiscal-explorer/1.0 (+https://github.com/Tomas-Boschetto/oecd-fiscal-explorer)"}

QUICK = {
    "DF_NAAG_VI.csv": f"{OECD}/OECD.SDD.NAD,DSD_NAAG_VI@DF_NAAG_VI,/all?format=csvfilewithlabels",
    "GDP_USD.csv": f"{OECD}/OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE1_EXPENDITURE,/A....B1GQ.....V..?format=csvfilewithlabels",
}
FULL = {
    "DF_TABLE11.csv": f"{OECD}/OECD.SDD.NAD,DSD_NASEC10@DF_TABLE11,/all?format=csvfilewithlabels",
    "DF_TABLE12.csv": f"{OECD}/OECD.SDD.NAD,DSD_NASEC10@DF_TABLE12,/all?format=csvfilewithlabels",
    "NipaDataA.txt": "https://apps.bea.gov/national/Release/TXT/NipaDataA.txt",
    "SeriesRegister.txt": "https://apps.bea.gov/national/Release/TXT/SeriesRegister.txt",
}
CMS_ZIP = "https://www.cms.gov/files/zip/national-health-expenditures-type-service-and-source-funds-cy-1960-2023.zip"
REVSTATS = f"{OECD}/OECD.CTP.TPS,DSD_REV_COMP_OECD@DF_RSOECD,/.TAX_REV.S13.{{codes}}._T.XDC.A?format=csvfilewithlabels&startPeriod=1995"

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as r: return r.read()

def save(name, url):
    path = f"{RAW}/{name}"
    print(f"  {name} ...", end=" ", flush=True)
    data = fetch(url)
    open(path, "wb").write(data)
    print(f"{len(data) / 1e6:.1f} MB")

def revstats(codes, out, with_label):
    print(f"  {os.path.basename(out)} ...", end=" ", flush=True)
    text = fetch(REVSTATS.format(codes="+".join(codes))).decode("utf-8-sig")
    rows = [r for r in csv.DictReader(io.StringIO(text)) if r["OBS_VALUE"]]
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["REF_AREA", "YEAR", "CODE"] + (["LABEL"] if with_label else []) + ["VALUE_XDC", "UNIT_MULT"])
        for r in rows:
            w.writerow([r["REF_AREA"], r["TIME_PERIOD"], r["STANDARD_REVENUE"]] + ([r["Revenue category"]] if with_label else [])
                       + [r["OBS_VALUE"], r["UNIT_MULT"]])
    print(f"{len(rows)} rows")

if __name__ == "__main__":
    full = "--full" in sys.argv
    os.makedirs(f"{RAW}/cms", exist_ok=True); os.makedirs(PROC, exist_ok=True)
    print("OECD National Accounts")
    for n, u in QUICK.items(): save(n, u)
    print("OECD Revenue Statistics")
    revstats(["T_1100", "T_1200", "T_1300"], f"{PROC}/revstats_income_tax_split.csv", False)
    revstats(["T_5111", "T_5112", "T_5113", "T_5121", "T_5123"], f"{PROC}/revstats_consumption_taxes.csv", True)
    if full:
        print("Large tables (this can take a while)")
        for n, u in FULL.items(): save(n, u)
        print("  CMS National Health Expenditure Accounts ...", end=" ", flush=True)
        z = zipfile.ZipFile(io.BytesIO(fetch(CMS_ZIP)))
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv") and "/" not in n and ".." not in n]
        nhe = [n for n in csvs if n.upper().startswith("NHE")]
        if not nhe: sys.exit("CMS zip has no NHE*.csv; check the URL on cms.gov (National Health Expenditure Data > Historical)")
        open(f"{RAW}/cms/NHE.csv", "wb").write(z.read(nhe[0]))
        print(f"{nhe[0]} -> data/raw/cms/NHE.csv")
    print("Done.")
