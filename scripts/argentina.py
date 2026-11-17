"""Argentina: download and map to the explorer's categories.

Argentina is not an OECD member, so it is missing from the OECD national-accounts tables the explorer uses.
This script builds comparable figures from other public sources:

  Totals (revenue, spending, balance, gross debt), GDP in US$:
      IMF Fiscal Monitor / World Economic Outlook (DataMapper API), general government.
  Spending by function:
      Argentina, Ministerio de Economía, "Gasto Público Consolidado" (nation + provinces + municipalities),
      % of GDP, via the datos.gob.ar series API. Mapped to COFOG (see MAP below). The split is applied to the
      IMF spending total, so only the shares come from this source.
  Defence vs public order:
      The Argentine series combines "Defensa y seguridad". Defence is taken from SIPRI military expenditure
      (via the World Bank API, MS.MIL.XPND.GD.ZS); the remainder is counted as police and public order.
  Tax revenue by type:
      OECD Revenue Statistics in Latin America and the Caribbean (DF_RSLAC), % of GDP, mapped to the
      national-accounts groups used for OECD countries.

Writes data/raw/argentina/* (downloads) and data/processed/argentina.json (one record per year, same field names
as the rows in data/explorer_data.json).

Usage (from the repository root):
  python3 scripts/argentina.py             # download and build
  python3 scripts/argentina.py --offline   # rebuild from the files already in data/raw/argentina
"""
import csv, io, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, OUT = f"{ROOT}/data/raw/argentina", f"{ROOT}/data/processed/argentina.json"
UA = {"User-Agent": "public-finance-explorer/1.0 (+https://github.com/Tomas-Boschetto/public-finance-explorer)"}
LAST_ACTUAL = 2024   # IMF figures after this year are projections and are left out

# Gasto Público Consolidado, % of GDP (datos.gob.ar series ids) -> short names
GPC = {
    "451.2_GPC_PIBPIB_0_0_7_85": "total",
    "451.2_GPC_ADMINIPIB_0_0_30_95": "admin", "451.2_GPC_SERVICPIB_0_0_31_0": "deuda", "451.2_GPC_CIENCIPIB_0_0_23_49": "ciencia",
    "451.2_GPC_DEFENSPIB_0_0_25_92": "defseg", "451.2_GPC_JUSTICPIB_0_0_16_34": "justicia",
    "451.2_GPC_PRODUCPIB_0_0_27_78": "prod_primaria", "451.2_GPC_ENERGIPIB_0_0_27_77": "energia", "451.2_GPC_INDUSTPIB_0_0_17_9": "industria",
    "451.2_GPC_TRANSPPIB_0_0_18_36": "transporte", "451.2_GPC_COMUNIPIB_0_0_22_72": "comunicaciones", "451.2_GPC_OTROS_PIB_0_0_34_36": "otros_econ",
    "451.2_GPC_OTROS_PIB_0_0_31_33": "serv_urbanos", "451.2_GPC_VIVIENPIB_0_0_26_20": "vivienda", "451.2_GPC_AGUA_APIB_0_0_27_47": "agua",
    "451.2_GPC_ATENCIPIB_0_0_22_83": "salud_publica", "451.2_GPC_OBRAS_PIB_0_0_28_43": "salud_obras_sociales", "451.2_GPC_INSSJYPIB_0_0_21_88": "salud_pami",
    "451.2_GPC_CULTURPIB_0_0_15_65": "cultura", "451.2_GPC_EDUCACPIB_0_0_24_72": "educ_basica", "451.2_GPC_EDUCACPIB_0_0_31_23": "educ_superior",
    "451.2_GPC_EDUCACPIB_0_0_41_18": "educ_otra", "451.2_GPC_PREVISPIB_0_0_24_25": "prevision", "451.2_GPC_ASIGNAPIB_0_0_31_49": "asignaciones",
    "451.2_GPC_PROGRAPIB_0_0_24_20": "empleo", "451.2_GPC_PROMOCPIB_0_0_35_59": "asistencia", "451.2_GPC_OBRAS_PIB_0_0_35_89": "obras_sociales_prest",
    "451.2_GPC_INSSJYPIB_0_0_28_35": "pami_prest",
}
# COFOG level 2 <- Argentine functions ("mil" = SIPRI defence, "seguridad" = defseg minus defence)
MAP = {
    "0101": ["admin"], "0104": ["ciencia"], "0107": ["deuda"],
    "0201": ["mil"],
    "0301": ["seguridad"], "0303": ["justicia"],
    "0402": ["prod_primaria"], "0403": ["energia"], "0404": ["industria"], "0405": ["transporte"], "0406": ["comunicaciones"], "0409": ["otros_econ"],
    "0501": ["serv_urbanos"],                       # municipal urban services: mostly waste collection and street cleaning
    "0601": ["vivienda"], "0603": ["agua"],           # water and sewerage combined, shown under water supply
    "0802": ["cultura"],
    "0901": ["educ_basica"], "0904": ["educ_superior"], "0908": ["educ_otra"],
    "1002": ["prevision"], "1004": ["asignaciones"], "1005": ["empleo"], "1007": ["asistencia"], "1009": ["obras_sociales_prest", "pami_prest"],
}
HEALTH = ["salud_publica", "salud_obras_sociales", "salud_pami"]   # no COFOG split possible: health has level 1 only

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r: return r.read()

def download():
    os.makedirs(RAW, exist_ok=True)
    jobs = {"gasto_publico_consolidado_pct_pib.csv": "https://apis.datos.gob.ar/series/api/series/?ids=" + ",".join(GPC) + "&format=csv&limit=1000&header=ids",
            "oecd_revstats_lac_arg.csv": "https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_REV_COMP_LAC@DF_RSLAC,/ARG.TAX_REV.S13.._T.PT_B1GQ.A?format=csvfilewithlabels",
            "worldbank_military_expenditure.json": "https://api.worldbank.org/v2/country/ARG/indicator/MS.MIL.XPND.GD.ZS?format=json&per_page=100"}
    for ind in ("GGR_G01_GDP_PT", "G_X_G01_GDP_PT", "GGXCNL_G01_GDP_PT", "G_XWDG_G01_GDP_PT", "NGDPD", "PPPGDP"):
        jobs[f"imf_{ind}.json"] = f"https://www.imf.org/external/datamapper/api/v1/{ind}/ARG"
    for name, url in jobs.items():
        print(f"  {name} ...", end=" ", flush=True); data = fetch(url); open(f"{RAW}/{name}", "wb").write(data); print(f"{len(data) / 1e3:.0f} kB")

def imf(ind):
    d = json.load(open(f"{RAW}/imf_{ind}.json"))["values"]
    return {int(y): v for y, v in d[next(iter(d))]["ARG"].items() if int(y) <= LAST_ACTUAL}

def build():
    rev, exp, bal, debt = imf("GGR_G01_GDP_PT"), imf("G_X_G01_GDP_PT"), imf("GGXCNL_G01_GDP_PT"), imf("G_XWDG_G01_GDP_PT")
    gdp_exc, gdp_ppp = imf("NGDPD"), imf("PPPGDP")
    mil = {int(x["date"]): x["value"] for x in json.load(open(f"{RAW}/worldbank_military_expenditure.json"))[1] if x["value"] is not None}
    gpc = {}
    for r in csv.DictReader(open(f"{RAW}/gasto_publico_consolidado_pct_pib.csv")):
        gpc[int(r["indice_tiempo"][:4])] = {GPC[k]: float(v) for k, v in r.items() if k in GPC and v not in ("", None)}
    tax = {}
    for r in csv.DictReader(open(f"{RAW}/oecd_revstats_lac_arg.csv", encoding="utf-8-sig")):
        if r["OBS_VALUE"]: tax.setdefault(int(r["TIME_PERIOD"]), {})[r["STANDARD_REVENUE"][2:]] = float(r["OBS_VALUE"])
    out = {}
    for y in sorted(set(rev) | set(exp)):
        if y not in rev or y not in exp: continue
        v = {"rev": round(rev[y], 3), "exp": round(exp[y], 3), "bal": round(bal.get(y, rev[y] - exp[y]), 3)}
        if y in debt: v["debt"] = round(debt[y], 3)
        if y in gdp_exc: v["gdp_exc"] = round(gdp_exc[y], 2)
        if y in gdp_ppp: v["gdp_ppp"] = round(gdp_ppp[y], 2)
        g = gpc.get(y)
        if g and y in mil:
            g = dict(g); g["mil"] = min(mil[y], g["defseg"]); g["seguridad"] = g["defseg"] - g["mil"]
            l2 = {code: sum(g.get(k, 0.0) for k in keys) for code, keys in MAP.items()}
            f = {fn: sum(val for code, val in l2.items() if code[:2] == fn) for fn in ("01", "02", "03", "04", "05", "06", "08", "09", "10")}
            f["07"] = sum(g.get(k, 0.0) for k in HEALTH)
            for fn, val in f.items(): v["f" + fn] = round(val, 3)
            v["l2"] = {code: round(val, 3) for code, val in l2.items()}
            v["est"] = sorted({code[:2] for code in l2})
        t = tax.get(y)
        if t and "1000" in t:
            T = lambda *codes: sum(t.get(c, 0.0) for c in codes)
            rd = dict(pit=T("1100"), cit=T("1200"), oti=T("1300", "4200", "4110"),
                      gct=T("5110"), otp=T("5120", "5130", "5300", "4400"), opr=T("5200", "4120", "3000", "6000", "4500", "4600"),
                      sce=T("2200"), sch=T("2100", "2300", "2400"), sci=0.0)
            v["r_inc"] = round(rd["pit"] + rd["cit"] + rd["oti"], 3)
            v["r_prod"] = round(rd["gct"] + rd["otp"] + rd["opr"], 3)
            v["r_soc"] = round(rd["sce"] + rd["sch"], 3)
            v["r_cap"] = round(T("4300"), 3)
            v["rd"] = {k: round(x, 3) for k, x in rd.items()}
            v["inc_est"] = 1; v["prd_est"] = 1
        v["alt"] = 1   # figures from non-OECD sources
        out[str(y)] = v
    json.dump(out, open(OUT, "w"), indent=0, separators=(",", ":"))
    y = max(k for k in out if "f07" in out[k])
    print(f"Argentina: {len(out)} years ({min(out)}-{max(out)}); spending by function to {y}; "
          f"{y}: spending {out[y]['exp']}%, health {out[y]['f07']}%, social protection {out[y]['f10']}% of GDP (before scaling)")

if __name__ == "__main__":
    if "--offline" not in sys.argv: download()
    build()
