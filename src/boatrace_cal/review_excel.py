"""Excel workbook export for analyst-confirmed review checklists."""

from collections.abc import Sequence
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from boatrace_cal.reviews import ConfirmedReviewList


_WORKSHEET_HEADERS = (
    "recommendation_id",
    "race_id",
    "stake_units",
    "notes",
    "reviewed_at",
    "reviewed_by",
)
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def export_confirmed_review_list_xlsx(
    review_list: ConfirmedReviewList,
    path: Path | str,
) -> Path:
    """Write a confirmed review checklist as a minimal XLSX workbook."""

    if type(review_list) is not ConfirmedReviewList:
        raise TypeError("review_list must be a ConfirmedReviewList")

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[object, ...]] = [
        ("boatraceCal confirmed review list",),
        ("business_date", review_list.business_date),
        ("generated_at", review_list.generated_at.isoformat()),
        ("generated_by", review_list.generated_by),
        ("risk_notice", review_list.risk_notice),
        ("total_stake_units", review_list.total_stake_units),
        (),
        _WORKSHEET_HEADERS,
    ]
    rows.extend(
        (
            entry.recommendation_id,
            entry.race_id,
            entry.stake_units,
            entry.notes,
            entry.reviewed_at.isoformat(),
            entry.reviewed_by,
        )
        for entry in review_list.entries
    )

    with ZipFile(output_path, mode="w") as workbook:
        _write_workbook_part(workbook, "[Content_Types].xml", _content_types_xml())
        _write_workbook_part(workbook, "_rels/.rels", _package_relationships_xml())
        _write_workbook_part(workbook, "docProps/app.xml", _app_properties_xml())
        _write_workbook_part(workbook, "docProps/core.xml", _core_properties_xml(review_list))
        _write_workbook_part(workbook, "xl/workbook.xml", _workbook_xml())
        _write_workbook_part(workbook, "xl/_rels/workbook.xml.rels", _workbook_relationships_xml())
        _write_workbook_part(workbook, "xl/styles.xml", _styles_xml())
        _write_workbook_part(workbook, "xl/worksheets/sheet1.xml", _worksheet_xml(rows))
    return output_path


def _write_workbook_part(workbook: ZipFile, name: str, content: str) -> None:
    info = ZipInfo(name, _ZIP_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    workbook.writestr(info, content.encode("utf-8"))


def _worksheet_xml(rows: Sequence[Sequence[object]]) -> str:
    max_column_count = max(len(row) for row in rows)
    dimension = f"A1:{_cell_reference(max_column_count - 1, len(rows))}"
    rendered_rows = "\n".join(_row_xml(index + 1, row) for index, row in enumerate(rows))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="{dimension}"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <sheetData>
{rendered_rows}
  </sheetData>
  <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>
"""


def _row_xml(row_number: int, row: Sequence[object]) -> str:
    if not row:
        return f'    <row r="{row_number}"/>'
    cells = "".join(
        _cell_xml(_cell_reference(column_index, row_number), value)
        for column_index, value in enumerate(row)
    )
    return f'    <row r="{row_number}">{cells}</row>'


def _cell_xml(reference: str, value: object) -> str:
    if type(value) is int:
        return f'<c r="{reference}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{reference}" t="inlineStr"><is><t>{text}</t></is></c>'


def _cell_reference(column_index: int, row_number: int) -> str:
    return f"{_column_name(column_index)}{row_number}"


def _column_name(column_index: int) -> str:
    if column_index < 0:
        raise ValueError("column_index must not be negative")
    name = ""
    value = column_index
    while True:
        value, remainder = divmod(value, 26)
        name = f"{chr(65 + remainder)}{name}"
        if value == 0:
            return name
        value -= 1


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""


def _package_relationships_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def _workbook_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="confirmed_reviews" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""


def _workbook_relationships_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
"""


def _app_properties_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>boatraceCal</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>1</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>confirmed_reviews</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
</Properties>
"""


def _core_properties_xml(review_list: ConfirmedReviewList) -> str:
    created = escape(review_list.generated_at.isoformat())
    creator = escape(review_list.generated_by)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>{creator}</dc:creator>
  <cp:lastModifiedBy>{creator}</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>
"""
