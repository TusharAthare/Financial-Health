"""Bank-specific PDF statement adapters."""

from services.internal.pdf_adapters.base import BankPdfAdapter
from services.internal.pdf_adapters.hdfc import HdfcPdfAdapter
from services.internal.pdf_adapters.icici import IciciPdfAdapter

PDF_ADAPTERS: tuple[BankPdfAdapter, ...] = (
    HdfcPdfAdapter(),
    IciciPdfAdapter(),
)

__all__ = (
    "BankPdfAdapter",
    "HdfcPdfAdapter",
    "IciciPdfAdapter",
    "PDF_ADAPTERS",
)
