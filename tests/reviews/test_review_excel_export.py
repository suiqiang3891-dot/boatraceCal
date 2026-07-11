from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from boatrace_cal.review_excel import export_confirmed_review_list_xlsx
from boatrace_cal.reviews import ConfirmedReviewEntry, ConfirmedReviewList


def test_export_confirmed_review_list_xlsx_writes_auditable_workbook(tmp_path: Path) -> None:
    output_path = tmp_path / "exports" / "confirmed.xlsx"
    review_list = ConfirmedReviewList(
        business_date="2025-01-02",
        generated_at=datetime(2026, 7, 11, 4, 0, tzinfo=UTC),
        generated_by="analyst",
        risk_notice="historical performance does not guarantee future results",
        entries=(
            ConfirmedReviewEntry(
                recommendation_id="rec-1",
                race_id="20250102-01-01",
                stake_units=3,
                notes="keep",
                reviewed_at=datetime(2026, 7, 11, 3, 20, tzinfo=UTC),
                reviewed_by="analyst",
            ),
            ConfirmedReviewEntry(
                recommendation_id="rec-2",
                race_id="20250102-01-02",
                stake_units=1,
                notes="late odds checked",
                reviewed_at=datetime(2026, 7, 11, 3, 30, tzinfo=UTC),
                reviewed_by="analyst",
            ),
        ),
    )

    exported_path = export_confirmed_review_list_xlsx(review_list, output_path)

    assert exported_path == output_path
    with ZipFile(output_path) as workbook:
        assert {
            "[Content_Types].xml",
            "_rels/.rels",
            "docProps/app.xml",
            "docProps/core.xml",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
            "xl/styles.xml",
            "xl/worksheets/sheet1.xml",
        }.issubset(set(workbook.namelist()))
        rows = _worksheet_rows(workbook.read("xl/worksheets/sheet1.xml"))

    assert rows[:6] == [
        ["boatraceCal confirmed review list"],
        ["business_date", "2025-01-02"],
        ["generated_at", "2026-07-11T04:00:00+00:00"],
        ["generated_by", "analyst"],
        ["risk_notice", "historical performance does not guarantee future results"],
        ["total_stake_units", "4"],
    ]
    assert rows[7:] == [
        [
            "recommendation_id",
            "race_id",
            "stake_units",
            "notes",
            "reviewed_at",
            "reviewed_by",
        ],
        ["rec-1", "20250102-01-01", "3", "keep", "2026-07-11T03:20:00+00:00", "analyst"],
        [
            "rec-2",
            "20250102-01-02",
            "1",
            "late odds checked",
            "2026-07-11T03:30:00+00:00",
            "analyst",
        ],
    ]


def _worksheet_rows(sheet_xml: bytes) -> list[list[str]]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ElementTree.fromstring(sheet_xml)
    rows: list[list[str]] = []
    for row in root.findall(".//main:sheetData/main:row", namespace):
        values: list[str] = []
        for cell in row.findall("main:c", namespace):
            inline_text = cell.find("main:is/main:t", namespace)
            if inline_text is not None:
                values.append(inline_text.text or "")
                continue
            number = cell.find("main:v", namespace)
            values.append(number.text if number is not None and number.text is not None else "")
        rows.append(values)
    return rows
