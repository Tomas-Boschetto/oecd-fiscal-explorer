"""Extracts all COFOG level-1 and level-2 general-government spending (national currency) from OECD Table 11
and converts it to % of GDP. Input: DF_TABLE11.csv (OECD.SDD.NAD,DSD_NASEC10@DF_TABLE11), GDP_USD.csv.
Usage (from the repository root):
  python3 scripts/extract_cofog_level2.py data/raw/DF_TABLE11.csv data/raw/GDP_USD.csv data/processed/cofog_level2.csv data/processed/cofog_labels.json"""
import csv,sys,json,collections
src,gdpf,out,labf=sys.argv[1:]
gdp={}
for r in csv.DictReader(open(gdpf,encoding="utf-8-sig")):
    if r["UNIT_MEASURE"]=="XDC" and r["OBS_VALUE"]: gdp[(r["REF_AREA"],r["TIME_PERIOD"])]=float(r["OBS_VALUE"])
rows=[]; labels={}; cov=collections.defaultdict(set)
with open(src,encoding="utf-8-sig",newline="") as fh:
    for r in csv.DictReader(fh):
        e=r["EXPENDITURE"]
        if not(e.startswith("GF") and len(e) in(4,6)) or not r["OBS_VALUE"]: continue
        if r["SECTOR"]!="S13" or r["TRANSACTION"]!="OTE" or r["UNIT_MEASURE"]!="XDC": continue
        labels[e]=r["Expenditure"]; g=gdp.get((r["REF_AREA"],r["TIME_PERIOD"]))
        if len(e)==6: cov[e[:4]].add(r["REF_AREA"])
        rows.append([r["REF_AREA"],r["TIME_PERIOD"],e,r["OBS_VALUE"],round(float(r["OBS_VALUE"])/g*100,4) if g else ""])
w=csv.writer(open(out,"w",newline="")); w.writerow(["REF_AREA","YEAR","COFOG","VALUE_XDC_MN","PCT_GDP"]); w.writerows(rows)
json.dump(labels,open(labf,"w"),indent=1,ensure_ascii=False)
print(len(rows),"rows")
for f in sorted(cov): print(f,labels.get(f),"| level-2 codes:",sorted(k for k in labels if k.startswith(f) and len(k)==6).__len__(),"| countries with level 2:",len(cov[f]), "| USA" if "USA" in cov[f] else "| no USA")
