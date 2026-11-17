# OECD Fiscal Balance Explorer

**Open the dashboard: https://tomas-boschetto.github.io/oecd-fiscal-explorer/** · Download the data: [`data/explorer_dataset.csv`](data/explorer_dataset.csv)

An interactive dashboard and an open dataset comparing **general government spending, revenue and deficits** across
OECD countries, 1995–2024, with a drill-down from main categories to subcategories:

- **Spending** by function (COFOG): social protection, health, education, general public services, economic affairs,
  defence, public order, and housing/environment/culture. Each splits into its official subcategories, for example
  Health into hospitals, outpatient care, medical products, public health, R&D and other.
- **Revenue** by source: income taxes, taxes on production and imports, social contributions, and other revenue.
  Each splits further, for example personal vs corporate income tax, or VAT and sales taxes vs excise.
- **Balance**: revenue minus spending (net lending / borrowing).

Everything is general government (central, state and local government plus social security funds), on the national
accounts basis (SNA 2008), so countries are comparable. **Argentina** is also included, built from other public
sources because it isn't in the OECD national accounts (see *Method*); treat its figures as approximate.

The whole dashboard is one file, `index.html`, with the data built in. It runs offline in any modern browser and
needs no server, account or installation.

## Use the dashboard

Open it online at https://tomas-boschetto.github.io/oecd-fiscal-explorer/, or use it offline:

1. Download the repository: **Code → Download ZIP** on GitHub, or `git clone https://github.com/Tomas-Boschetto/oecd-fiscal-explorer.git`.
2. Open `index.html` in a browser.

What you can do:

| Control | What it does |
|---|---|
| **Single year / Period** | Show one year (▶ Play steps through the years) or a range such as 2015–2023. |
| **Unit** | % of GDP, US$ billions at purchasing-power parity, or US$ billions at market exchange rates. Over a period, US$ figures are summed (cumulative) and % of GDP is the share of the period's combined GDP. |
| **Break down** | Spending or Revenue. |
| **Detail** | Main categories, or the subcategories of one category. Clicking a coloured segment does the same; **← All categories** goes back. |
| **Sort by** | Total, the comparison total, balance, name, or any single category. The category you sort by is drawn first, from the zero line. |
| **Categories** | Turn categories or subcategories on and off. |
| **Countries** | Pick countries one by one or by group (OECD, EU, G7, Nordics, English-speaking, Latin America). Optionally add non-OECD economies and EU / euro-area totals. |
| **Only countries with complete data** | Hide countries missing any year in the chosen period. The excluded countries are listed under the chart. |
| **Show as table / Copy data as CSV** | See or copy the exact numbers behind the current view. |

The dashboard has three tabs: **Explorer** (the chart), **Categories** (what each spending category, revenue source and subcategory contains) and **About the data** (how to use it, method, estimates, sources and licences).

In the main views, a thin dark bar under each country shows the other side of the budget (revenue under spending,
spending under revenue), and the right-hand column shows the balance. Subcategory views show only the breakdown.

## Use the data

| File | What it is |
|---|---|
| `data/explorer_dataset.csv` | **Start here.** Every value in the dashboard, one value per row (about 94,000 rows). |
| `data/explorer_data.json` | The same data in the compact form the dashboard uses. |
| `data/processed/*` | Intermediate extracts from the sources (see *Rebuild*), useful if you want to redo a step differently. |

Columns of `explorer_dataset.csv`:

| Column | Meaning |
|---|---|
| `country_code`, `country` | ISO 3-letter code and OECD name. Also includes Argentina (ARG, all values `estimated = 1`), some other non-OECD economies (BRA, CHN, IDN, RUS, ZAF) and aggregates (EU, EA). |
| `year` | Calendar year. |
| `group` | `total`, `gdp`, `spending` or `revenue`. |
| `code` | Spending: COFOG code, `07` (level 1) or `0703` (level 2). Revenue: `inc`, `prod`, `soc` (level 1) or e.g. `income.pit` (level 2). Totals: `revenue`, `spending`, `balance`, `gross_debt`. |
| `name` | Plain-language label. |
| `level` | 0 = totals, 1 = main category, 2 = subcategory. |
| `value` | The number. |
| `unit` | `pct_gdp` (% of GDP) or `usd_bn` (US$ billions, for GDP rows). |
| `estimated` | `1` where the value is an estimate (see *Method*), otherwise `0`. |
| `source` | Where the value comes from. |

Example, in Python with pandas:

```python
import pandas as pd
df = pd.read_csv("data/explorer_dataset.csv", dtype={"code": str})  # keep codes like "07" as text
health = df[(df.code.str.startswith("07")) & (df.level == 2) & (df.year == 2023)]
print(health.pivot(index="country", columns="name", values="value").round(2))
```

Values are as published; the dashboard additionally rescales subcategories so they add up exactly to their parent
category (see below). The CSV keeps the published values, so subcategories may differ slightly from their total.

## Method and caveats

- **Totals** (revenue, spending, balance, categories) come from OECD *National Accounts at a Glance*, chapter 6, in
  % of GDP. Revenue minus spending equals the published balance for every country and year.
- **Spending subcategories** come from OECD Table 11 (COFOG level 2). They exist for 37 OECD countries.
  Some countries' level-2 figures don't add up exactly to the level-1 total. The dashboard scales them in proportion
  (usually by under 0.5 points of GDP, at most 2.4).
- **United States spending subcategories are estimates.** The US reports no COFOG subcategories to the OECD. The US
  total for each category is the OECD figure, and only the split inside it is estimated:
  - Health: [CMS National Health Expenditure Accounts](https://www.cms.gov/data-research/statistics-trends-and-reports/national-health-expenditure-data/historical),
    government-funded spending only (Medicare, Medicaid, CHIP, veterans' and military health care, other public
    programmes, public health, public research and investment), mapped to COFOG 07.1–07.6.
  - Other categories: [BEA NIPA table 3.16](https://apps.bea.gov/iTable/?reqid=19&step=2&isuri=1&categories=survey#eyJhcHBpZCI6MTksInN0ZXBzIjpbMSwyLDNdLCJkYXRhIjpbWyJjYXRlZ29yaWVzIiwiU3VydmV5Il0sWyJOSVBBX1RhYmxlX0xpc3QiLCI1MDMiXV19),
    government current expenditures by function. BEA has fewer lines: primary and secondary education are one line
    (shown under 9.1), and defence, environment, housing and culture have no split.
- **Revenue subcategories** come from OECD Table 12. Two adjustments, marked `estimated = 1`:
  - *Personal vs corporate income tax*: where the national accounts don't split them (about half the countries,
    including the US; some report zeros instead of leaving the cells empty), the split comes from
    [OECD Revenue Statistics](https://www.oecd.org/en/topics/sub-issues/global-tax-revenues.html) (codes 1100 / 1200 / 1300),
    applied to the national-accounts total.
  - *General consumption taxes*: national accounts count only VAT as VAT and put retail sales taxes (e.g. US state
    sales taxes) with excise duties. For comparability, sales and other general turnover taxes (Revenue Statistics
    5112 + 5113) are moved next to VAT. Revenue Statistics lags by a year or two, so its latest ratio is carried
    forward for up to two years.
- **Argentina** is not an OECD member and is missing from the OECD national accounts, so all its values are marked
  `estimated = 1` and come from:
  - Totals (revenue, spending, balance, gross debt) and GDP in US$: [IMF Fiscal Monitor / World Economic Outlook](https://www.imf.org/external/datamapper/),
    general government, 1995–2024 (later IMF years are projections and are left out).
  - Spending by function: Argentina's Ministry of Economy, [Gasto Público Consolidado](https://datos.gob.ar/dataset/sspm-gasto-publico-consolidado)
    (nation, provinces and municipalities), up to 2023, mapped to COFOG. Its total is higher than the IMF's
    (41.9% vs 37.3% of GDP in 2023, a difference in coverage), so only its shares are used and they are scaled to the
    IMF total. Defence and security are one line there: defence is taken from SIPRI military expenditure
    ([World Bank API](https://data.worldbank.org/indicator/MS.MIL.XPND.GD.ZS)) and the rest is counted as police and
    public order. Health has no subcategories; water and sewerage are shown under water supply; municipal urban services
    under waste management.
  - Taxes: OECD Revenue Statistics in Latin America and the Caribbean, mapped to the national-accounts groups (e.g.
    the provincial turnover tax, *Ingresos Brutos*, counts as a general consumption tax; the tax on bank transactions
    and export duties as other taxes on products). "Other revenue" is the IMF total minus taxes and has no breakdown.
- **What "health" and other categories cover** follows COFOG. For example, health excludes cash sickness benefits and
  much long-term care (both under social protection), and compulsory private insurance (e.g. Switzerland) is not
  government spending.
- **The balance can't be split by category.** Government revenue is pooled, so no part of a deficit belongs to a
  particular spending category. This is why subcategory views don't show the balance.
- **Coverage.** Most OECD countries have full data from 1995. Recent years are missing for some (e.g. Japan, Canada,
  New Zealand), and Türkiye and Australia lack revenue detail.

## Rebuild or update the data

Requirements: Python 3.8 or later. No packages to install. Run all commands from the repository root.

**Quick rebuild** (refreshes totals, GDP and Revenue Statistics; about 35 MB of downloads, a minute or two):

```bash
python3 scripts/download_sources.py
python3 scripts/build_data.py
```

**Argentina** (small downloads from the IMF, datos.gob.ar, the World Bank and the OECD):

```bash
python3 scripts/argentina.py
python3 scripts/build_data.py
```

**Full rebuild** (also re-extracts all subcategories; downloads about 3.5 GB, mostly OECD Table 11):

```bash
python3 scripts/download_sources.py --full
python3 scripts/extract_cofog_level2.py data/raw/DF_TABLE11.csv data/raw/GDP_USD.csv data/processed/cofog_level2.csv data/processed/cofog_labels.json
python3 scripts/extract_revenue_detail.py data/raw/DF_TABLE12.csv data/raw/GDP_USD.csv data/processed/revenue_detail.csv
python3 scripts/us_subcategories.py data/raw data/processed/us_cofog_shares.json
python3 scripts/build_data.py
```

Downloads go to `data/raw/`, which is not committed. `build_data.py` writes `index.html`, `data/explorer_data.json`
and `data/explorer_dataset.csv`. To change the dashboard itself, edit `src/template.html` and run `build_data.py`
again.

If CMS publishes a newer health spending file, update `CMS_ZIP` in `scripts/download_sources.py` with the new link
from the [CMS historical data page](https://www.cms.gov/data-research/statistics-trends-and-reports/national-health-expenditure-data/historical).

## Repository layout

```
index.html                     the dashboard (generated)
data/explorer_dataset.csv      all values, long format (generated)
data/explorer_data.json        compact data used by the dashboard (generated)
data/processed/                extracts from the large source tables
data/raw/                      source downloads (not committed)
scripts/download_sources.py    downloads the sources
scripts/extract_*.py           extract subcategories from OECD tables 11 and 12
scripts/us_subcategories.py    US subcategory shares from BEA and CMS
scripts/argentina.py           Argentina from IMF, Ministry of Economy, SIPRI and OECD LAC
scripts/build_data.py          builds the dataset and the dashboard
src/template.html              dashboard source
```

## Sources and licences

| Source | Used for | Terms |
|---|---|---|
| OECD National Accounts: *National Accounts at a Glance* ch. 6; Tables 1, 11 and 12 ([OECD Data Explorer](https://data-explorer.oecd.org/)) | Totals, categories, subcategories, revenue detail, GDP | OECD data are published under [CC BY 4.0](https://www.oecd.org/en/about/terms-conditions.html) |
| OECD Revenue Statistics | Income-tax split, sales taxes | Same as above |
| US Bureau of Economic Analysis, NIPA table 3.16 | US spending subcategories (except health) | US government work, public domain |
| US Centers for Medicare & Medicaid Services, National Health Expenditure Accounts | US health subcategories | US government work, public domain |
| IMF Fiscal Monitor and World Economic Outlook | Argentina totals and GDP | [IMF terms](https://www.imf.org/en/About/copyright-and-terms) (reuse with attribution) |
| Argentina, Ministerio de Economía: Gasto Público Consolidado (datos.gob.ar) | Argentina spending by function | [datos.gob.ar terms](https://datos.gob.ar/acerca/seccion/terminos-y-condiciones) |
| SIPRI Military Expenditure Database, via the World Bank | Argentina defence | [World Bank data licence](https://datacatalog.worldbank.org/public-licenses); credit SIPRI |
| OECD Revenue Statistics in Latin America and the Caribbean | Argentina taxes | OECD terms (CC BY 4.0) |

When you reuse the data, credit the original sources (e.g. "Source: OECD; US detail: BEA, CMS; compiled by
OECD Fiscal Balance Explorer"). The code in this repository is released under the MIT licence (see `LICENSE`).
This is an independent project and is not affiliated with or endorsed by the OECD, BEA, CMS, the IMF, SIPRI or the Argentine government.
