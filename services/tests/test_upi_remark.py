"""Unit tests for UPI remark extraction."""

from django.test import SimpleTestCase

from services.domain.upi_remark import extract_upi_remark, resolve_normalized_merchant


class UpiRemarkTests(SimpleTestCase):
    """Tests for trailing UPI note parsing."""

    def test_extracts_trailing_user_note(self) -> None:
        """Trailing hyphen segment is returned as the remark."""
        raw = (
            "UPI-KADAM DAIRY-GPAY-11256235418@OKBIZAX "
            "IS-UTIB0000553-764821284164-PANNER"
        )
        self.assertEqual(extract_upi_remark(raw), "panner")

    def test_rejects_numeric_trailing_ref(self) -> None:
        """Long numeric tail is not treated as a user note."""
        raw = "UPI-SHOP-GPAY-9876543210@OKAXIS-UTIB0000553-764821284164"
        self.assertIsNone(extract_upi_remark(raw))

    def test_rejects_ifsc_as_tail(self) -> None:
        """IFSC codes are not user notes."""
        raw = "UPI-MERCHANT-UTIB0000553"
        self.assertIsNone(extract_upi_remark(raw))

    def test_resolve_prefers_remark_over_payee(self) -> None:
        """Normalized merchant uses remark for categorization."""
        raw = "UPI-KADAM DAIRY-GPAY-11256235418@OKBIZAX IS-UTIB0000553-764821284164-PANEER"
        self.assertEqual(resolve_normalized_merchant(raw), "paneer")

    def test_rejects_bank_suffix_as_remark(self) -> None:
        """Bank suffix after VPA is not a user note."""
        raw = "UPI-JYOTIASHWINBHANDE-Q829201254@YBL-YES"
        self.assertIsNone(extract_upi_remark(raw))

    def test_resolve_falls_back_without_remark(self) -> None:
        """Without a remark, standard merchant normalization applies."""
        raw = "UPI-SWIGGY BANGALORE"
        normalized = resolve_normalized_merchant(raw)
        self.assertIn("swiggy", normalized.lower())
