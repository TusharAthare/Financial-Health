"""Validation rules for parsed PDF statement transactions."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from services.domain.transaction_row import ParsedTransactionRow

BALANCE_TOLERANCE = Decimal("0.02")


@dataclass(frozen=True)
class ValidationWarning:
    """Non-fatal parse validation issue."""

    code: str
    message: str


@dataclass
class ParseValidationResult:
    """Outcome of post-parse validation checks."""

    warnings: list[ValidationWarning] = field(default_factory=list)
    row_count: int = 0
    dates_monotonic: bool = True
    balance_continuity_ok: bool = True

    @property
    def has_warnings(self) -> bool:
        """Return True when any validation warnings were recorded."""
        return bool(self.warnings)


def validate_parsed_transactions(
    rows: list[ParsedTransactionRow],
) -> ParseValidationResult:
    """
    Validate row count, date order, and running-balance continuity.

    Balance checks apply only when consecutive rows include balances.
    """
    result = ParseValidationResult(row_count=len(rows))

    if not rows:
        result.warnings.append(
            ValidationWarning(
                code="empty_statement",
                message="No transactions were extracted from the PDF.",
            ),
        )
        return result

    _check_date_monotonicity(rows, result)
    _check_balance_continuity(rows, result)
    return result


def _check_date_monotonicity(
    rows: list[ParsedTransactionRow],
    result: ParseValidationResult,
) -> None:
    """Warn when transaction dates move backwards."""
    prev_date: date | None = None
    backward_count = 0

    for row in rows:
        if prev_date is not None and row.transaction_date < prev_date:
            backward_count += 1
        prev_date = row.transaction_date

    if backward_count:
        result.dates_monotonic = False
        result.warnings.append(
            ValidationWarning(
                code="date_non_monotonic",
                message=(
                    f"Transaction dates are not in chronological order "
                    f"({backward_count} backward step(s))."
                ),
            ),
        )


def _check_balance_continuity(
    rows: list[ParsedTransactionRow],
    result: ParseValidationResult,
) -> None:
    """Warn when running balances do not match amount deltas."""
    prev_balance: Decimal | None = None
    mismatch_count = 0

    for row in rows:
        if row.balance is None:
            continue

        if prev_balance is not None:
            expected = prev_balance + row.amount
            if abs(expected - row.balance) > BALANCE_TOLERANCE:
                mismatch_count += 1

        prev_balance = row.balance

    if mismatch_count:
        result.balance_continuity_ok = False
        result.warnings.append(
            ValidationWarning(
                code="balance_discontinuity",
                message=(
                    f"Closing balance does not match prior balance plus amount "
                    f"for {mismatch_count} row(s)."
                ),
            ),
        )
