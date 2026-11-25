"""The official statistics (milestone 6): the Ministry of Justice's count of the cases each district court
entered in register C each year, against intake's exact counts.

The source is InfoData's report S_AS_40, "Přehled o vyřizování agendy C u OS" (Tabulka č. 40), one for
each year. InfoData's report form (prehledy-agend.html) takes the report's code and a period, and lists
the matching documents, each with links to PDF, XML and HTML versions. The form needs a session, so a run
with anything to fetch loads the form page first.

The XML is an Excel 2003 spreadsheet. It has a block of rows for each region (a row per court, then the
region's total, "Celkem"), and a last block with a row per region and the national total. Each row has a
name and 22 numbers, under numbered columns. We keep four of them:
- "nápad" (the 2nd number): the cases newly entered in the register in the year;
- "obživlo" (the 1st and 3rd, by the rules before and after 2009): cases revived, which keep their number,
  so they aren't intake;
- "vyřízeno" (the 5th): cases disposed in the year;
- "nevyřízeno" (the 6th): cases not yet disposed at the end of the year.
At Náchod in 2022 these give nápad 2,309 and 108 revived, as V(MS)-114 does (see docs/plan.md).

Writes data/derived/official.csv: for each court and year, and for the whole country ("all"), intake's
count beside the report's numbers.

    uv run soudai official
"""

import csv
import html
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date

from . import intake, paths, reference
from .http import Client, UnexpectedResponse

SITE = "https://cslav.justice.cz"
FORM = SITE + "/InfoData/prehledy-agend.html"
REPORT = "S_AS_40"
YEARS = range(2020, 2026)
PATH = paths.DERIVED / "official.csv"
COLUMNS = ["court", "year", "registered", "napad", "revived", "disposed", "pending"]
SPREADSHEET = "{urn:schemas-microsoft-com:office:spreadsheet}"
NUMBERS = 22  # numbers in each court's row
REGIONS = 8  # rows in the last block: the old kraje, before the national total


def query(year):
    """The report form's fields for one year's report."""
    return {
        "sestavaQry": REPORT,
        "obdobiOdQry": f"01.01.{year}",
        "obdobiDoQry": f"31.12.{year}",
        "jenVykCeleObdQry": "on",  # only reports for the whole period
        "vyhledatPrehlAg": "Vyhledat",
    }


def document_link(page, year):
    """The XML link of the one report the form lists for the year, as a path on the site."""
    found = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cells = [re.sub(r"\s+", " ", cell).strip() for cell in re.findall(r"<td>(.*?)</td>", row, re.S)]
        if cells[:1] == [REPORT] and cells[2:4] == [f"01.01.{year}", f"31.12.{year}"]:
            found += re.findall(r'href="(/InfoData/servlet/FileServlet\?[^"]*id4=xml[^"]*)"', row)
    if len(found) != 1:
        raise UnexpectedResponse(f"{len(found)} XML documents of {REPORT} for {year}")
    return html.unescape(found[0])


def parse(content):
    """The spreadsheet's rows with a name and 22 numbers, as [(name, numbers)] in order, and the date the
    report was computed ("Datum výpočtu")."""
    rows, computed = [], None
    for row in ET.fromstring(content).iter(SPREADSHEET + "Row"):
        cells = [
            (cell.findtext(SPREADSHEET + "Data") or "").strip() for cell in row.iter(SPREADSHEET + "Cell")
        ]
        if computed is None and any("Datum výpočtu" in cell for cell in cells):
            computed = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", " ".join(cells)).groups()[::-1]
        if len(cells) != NUMBERS + 1 or cells[0] in ("", "a"):  # "a" heads the row numbering the columns
            continue
        if re.fullmatch(r"[\d,]+(\.\d+)?", cells[1]):
            rows.append((cells[0], [float(cell.replace(",", "")) for cell in cells[1:]]))
    if computed is None:
        raise UnexpectedResponse("no 'Datum výpočtu' in the report")
    return rows, date(*map(int, computed))


def numbers(values):
    return {
        "napad": round(values[1]),
        "revived": round(values[0] + values[2]),
        "disposed": round(values[4]),
        "pending": round(values[5]),
    }


def by_court(rows, courts):
    """{court code: numbers} for every court, and the national numbers. The report names courts without
    "Okresní soud" and the like ("Náchod", "Praha 1", "Brno" for Městský soud v Brně). Every court must
    appear once, the region rows must follow, and the national total must add up."""
    codes = {
        re.sub(r"^(Okresní|Obvodní|Městský) soud ", "", court["name"]).lower(): court["code"]
        for court in courts
    }
    found, others = {}, []
    for name, values in rows:
        code = codes.get(name.lower())
        if code is None:
            others.append((name, values))
        elif code in found:
            raise UnexpectedResponse(f"{name} appears twice")
        else:
            found[code] = numbers(values)
    missing = sorted(codes.keys() - {name.lower() for name, _ in rows})
    if missing:
        raise UnexpectedResponse(f"not in the report: {', '.join(missing)}")
    national = numbers(others[-1][1])
    regions = [name for name, _ in others if name != "Celkem"]
    if others[-1][0] != "Celkem" or len(regions) != REGIONS:
        raise UnexpectedResponse(f"expected {REGIONS} regions and a national total, got {regions}")
    for column, total in national.items():
        if sum(court[column] for court in found.values()) != total:
            raise UnexpectedResponse(f"the courts' {column} doesn't add up to the national {total:,}")
    return found, national


def registered():
    """Intake's count of cases registered, {(court, year): count}."""
    with open(intake.PATH, encoding="utf-8", newline="") as file:
        counts = defaultdict(int)
        for row in csv.DictReader(file):
            counts[row["court"], int(row["year"])] += int(row["count"] or 0)
    return counts


def fetch(client, year, session):
    """One year's report, as XML. `session()` loads the form page once, the first time it's needed."""
    if client.cached("POST", FORM, query(year), form=True) is None:
        session()
    page = client.post(FORM, query(year), form=True)
    if page.status != 200:
        raise UnexpectedResponse(f"HTTP {page.status} from the report form for {year}")
    link = SITE + document_link(page.content.decode("utf-8"), year)
    if client.cached("GET", link) is None:
        session()
    report = client.get(link)
    if report.status != 200 or not (report.content_type or "").startswith("text/xml"):
        raise UnexpectedResponse(f"HTTP {report.status} ({report.content_type}) for {year}'s report")
    return report.content


def run():
    courts = reference.courts()
    counts = registered()
    rows, documents = [], {}
    with Client("official") as client:
        loaded = []

        def session():
            if not loaded:
                client.get(FORM, refresh=True)
                loaded.append(True)

        for year in YEARS:
            table, computed = parse(fetch(client, year, session))
            found, national = by_court(table, courts)
            documents[str(year)] = computed.isoformat()
            for court in sorted(found):
                rows.append({"court": court, "year": year, "registered": counts[court, year]} | found[court])
            total = sum(counts[court, year] for court in found)
            rows.append({"court": "all", "year": year, "registered": total} | national)
    with open(PATH, "w", encoding="utf-8", newline="\n") as file:
        writer = csv.DictWriter(file, COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    reference.update_sources(
        {
            "infodata": {
                "form": FORM,
                "report": f'{REPORT}, "Přehled o vyřizování agendy C u OS" (Tabulka č. 40)',
                "query": "POST, as a web form: " + ", ".join(f"{k}={v}" for k, v in query("YYYY").items()),
                "computed": documents,  # when each year's report was computed
                "checked": date.today().isoformat(),
            }
        }
    )
    print(f"Wrote {len(rows)} rows to {PATH}")
    for row in rows:
        if row["court"] == "all":
            gap = row["registered"] / row["napad"] - 1
            print(f"  {row['year']}: registered {row['registered']:,}, nápad {row['napad']:,} ({gap:+.2%})")
    return 0
