"""Extracts general-government revenue detail (national currency) from OECD Table 12 and converts it to % of GDP.
Input: DF_TABLE12.csv (OECD.SDD.NAD,DSD_NASEC10@DF_TABLE12), GDP_USD.csv.
Usage (from the repository root):
  python3 scripts/extract_revenue_detail.py data/raw/DF_TABLE12.csv data/raw/GDP_USD.csv data/processed/revenue_detail.csv"""
import csv,sys
src,gdpf,out=sys.argv[1:]
CODES={"OTR","D2","D21","D211","D29","D5","D51","D51M","D51O","D59","D61","D611","D613","D612_D614",
       "D4","D41","D4N","D7","D9","D91","P1O","D39"}
gdp={}
for r in csv.DictReader(open(gdpf,encoding="utf-8-sig")):
    if r["UNIT_MEASURE"]=="XDC" and r["OBS_VALUE"]: gdp[(r["REF_AREA"],r["TIME_PERIOD"])]=float(r["OBS_VALUE"])
rows=[]
with open(src,encoding="utf-8-sig",newline="") as fh:
    for r in csv.DictReader(fh):
        if r["SECTOR"]=="S13" and r["ACCOUNTING_ENTRY"]=="C" and r["TRANSACTION"] in CODES and r["OBS_VALUE"] and r["UNIT_MEASURE"]=="XDC":
            g=gdp.get((r["REF_AREA"],r["TIME_PERIOD"]))
            if g: rows.append([r["REF_AREA"],r["TIME_PERIOD"],r["TRANSACTION"],r["CONSOLIDATION"],round(float(r["OBS_VALUE"])/g*100,4)])
w=csv.writer(open(out,"w",newline="")); w.writerow(["REF_AREA","YEAR","TRANSACTION","CONSOLIDATION","PCT_GDP"]); w.writerows(rows)
print(len(rows),"rows")
