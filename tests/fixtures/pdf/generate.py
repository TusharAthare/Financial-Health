"""Generate text-based bank statement PDFs for parser golden-file tests."""

from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HDFC_ROWS = (
    ("01/06/2025", "UPI-SWIGGY BANGALORE", "450.00", "", "48550.00"),
    ("02/06/2025", "SALARY CREDIT ACME CORP", "", "75000.00", "123550.00"),
    ("03/06/2025", "NEFT-RENT PAYMENT", "15000.00", "", "108550.00"),
    ("05/06/2025", "UPI-NETFLIX SUBSCRIPTION", "649.00", "", "107901.00"),
)

ICICI_ROWS = (
    ("01/06/2025", "UPI-ZEPTO GROCERY", "892.50", "", "102008.50"),
    ("07/06/2025", "ATM WITHDRAWAL SBI MUMBAI", "5000.00", "", "97008.50"),
    ("15/06/2025", "EMI-HOME LOAN HDFC", "18500.00", "", "78508.50"),
    ("25/06/2025", "INTEREST CREDIT", "", "125.00", "78633.50"),
)


def _build_bank_pdf(
    output_path: Path,
    bank_title: str,
    headers: tuple[str, ...],
    data_rows: tuple[tuple[str, ...], ...],
) -> None:
    """Write a simple table-based statement PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    story = [
        Paragraph(bank_title, styles["Title"]),
        Spacer(1, 6 * mm),
        Paragraph("Account Statement", styles["Normal"]),
        Spacer(1, 4 * mm),
    ]

    table_data = [list(headers)] + [list(row) for row in data_rows]
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ],
        ),
    )
    story.append(table)
    doc.build(story)


def build_hdfc_pdf(output_path: Path) -> None:
    """Create an HDFC-style sample statement PDF."""
    _build_bank_pdf(
        output_path,
        "HDFC BANK",
        (
            "Date",
            "Narration",
            "Withdrawal Amt.",
            "Deposit Amt.",
            "Closing Balance",
        ),
        HDFC_ROWS,
    )


def build_icici_pdf(output_path: Path) -> None:
    """Create an ICICI-style sample statement PDF."""
    _build_bank_pdf(
        output_path,
        "ICICI BANK",
        (
            "Value Date",
            "Transaction Remarks",
            "Withdrawal Amount (INR)",
            "Deposit Amount (INR)",
            "Balance (INR)",
        ),
        ICICI_ROWS,
    )


def build_scanned_pdf(output_path: Path) -> None:
    """Create a PDF with no extractable text (blank page)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    doc.build([])


def build_password_pdf(output_path: Path, password: str = "secret123") -> None:
    """Create a password-protected HDFC-style PDF."""
    plain_path = output_path.with_suffix(".plain.pdf")
    build_hdfc_pdf(plain_path)

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(plain_path))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.encrypt(password)
    with open(output_path, "wb") as dest:
        writer.write(dest)
    plain_path.unlink(missing_ok=True)


def rows_to_golden(rows: tuple[tuple[str, ...], ...], debit_is_negative: bool = True) -> list[dict]:
    """Convert fixture rows to golden JSON transaction dicts."""
    golden: list[dict] = []
    for date_str, desc, debit, credit, balance in rows:
        debit_val = Decimal(debit) if debit else None
        credit_val = Decimal(credit) if credit else None
        if debit_val:
            amount = -abs(debit_val) if debit_is_negative else debit_val
        elif credit_val:
            amount = abs(credit_val)
        else:
            continue

        parts = date_str.split("/")
        iso_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
        golden.append(
            {
                "transaction_date": iso_date,
                "amount": str(amount),
                "raw_description": desc,
                "balance": balance or None,
            },
        )
    return golden
