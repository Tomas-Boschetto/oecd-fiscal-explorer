"""Debt by sector: government, households and non-financial companies, in % of GDP.

Source: IMF Global Debt Database (via the IMF DataMapper API)
  GG_DEBT_GDP  general government gross debt
  HH_LS        household debt, loans and debt securities
  NFC_LS       non-financial corporate debt, loans and debt securities
Where the Global Debt Database has no government debt for a country (Mexico, New Zealand, Argentina), the IMF World
Economic Outlook series GGXWDG_NGDP (general government gross debt) is used instead and the value is flagged.

Writes data/raw/debt/*.json (downloads) and data/processed/debt.json: {country: {year: {gov, hh, nfc, gov_weo}}}.

Usage (from the repository root):
  python3 scripts/debt.py             # download and build
  python3 scripts/debt.py --offline   # rebuild from the files already in data/raw/debt
"""
import json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, OUT = f"{ROOT}/data/raw/debt", f"{ROOT}/data/processed/debt.json"
UA = {"User-Agent": "public-finance-explorer/1.0 (+https://github.com/Tomas-Boschetto/public-finance-explorer)"}
SERIES = {"gov": "GG_DEBT_GDP", "hh": "HH_LS", "nfc": "NFC_LS", "gov_weo": "GGXWDG_NGDP"}
LAST_ACTUAL = 2024   # WEO values after this are projections

def download():
    os.makedirs(RAW, exist_ok=True)
    for ind in SERIES.values():
        print(f"  {ind} ...", end=" ", flush=True)
        req = urllib.request.Request(f"https://www.imf.org/external/datamapper/api/v1/{ind}", headers=UA)
        data = urllib.request.urlopen(req, timeout=300).read()
        open(f"{RAW}/{ind}.json", "wb").write(data); print(f"{len(data) / 1e6:.1f} MB")

def load(ind):
    v = json.load(open(f"{RAW}/{ind}.json"))["values"]
    return v[next(iter(v))]

def build():
    s = {k: load(ind) for k, ind in SERIES.items()}
    out = {}
    for c in set(s["hh"]) | set(s["nfc"]) | set(s["gov"]) | set(s["gov_weo"]):
        years = {}
        for k in ("gov", "hh", "nfc"):
            for y, v in s[k].get(c, {}).items():
                if v is not None and int(y) <= LAST_ACTUAL: years.setdefault(y, {})[k] = round(v, 2)
        if c not in s["gov"]:   # fall back to WEO for government debt
            for y, v in s["gov_weo"].get(c, {}).items():
                if v is not None and int(y) <= LAST_ACTUAL:
                    years.setdefault(y, {}).update(gov=round(v, 2), gov_weo=1)
        if years: out[c] = years
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    weo = sorted(c for c, ys in out.items() if any(v.get("gov_weo") for v in ys.values()))
    print(f"Debt: {len(out)} economies; government debt from WEO for {len(weo)} of them (e.g. {', '.join(weo[:8])})")

if __name__ == "__main__":
    if "--offline" not in sys.argv: download()
    build()
