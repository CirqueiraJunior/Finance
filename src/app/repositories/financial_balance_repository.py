from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial_balance_entry import FinancialBalanceEntry


class FinancialBalanceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, year: int, month: int, balance_type: str):
        return self.session.scalar(select(FinancialBalanceEntry).where(
            FinancialBalanceEntry.year == year, FinancialBalanceEntry.month == month,
            FinancialBalanceEntry.balance_type == balance_type))

    def base(self, year: int | None = None, month: int | None = None):
        statement = select(FinancialBalanceEntry).where(
            FinancialBalanceEntry.balance_type == "SALDO_INICIAL"
        )
        if year is not None and month is not None:
            statement = statement.where(
                FinancialBalanceEntry.year * 100 + FinancialBalanceEntry.month
                <= year * 100 + month
            )
        return self.session.scalar(statement.order_by(
            FinancialBalanceEntry.year.desc(), FinancialBalanceEntry.month.desc()
        ))

    def latest_applied_at_or_before(self, year: int, month: int):
        return self.session.scalar(select(FinancialBalanceEntry).where(
            FinancialBalanceEntry.balance_type == "SALDO_APLICADO",
            FinancialBalanceEntry.year * 100 + FinancialBalanceEntry.month
            <= year * 100 + month,
        ).order_by(
            FinancialBalanceEntry.year.desc(), FinancialBalanceEntry.month.desc()
        ))

    def add(self, entry: FinancialBalanceEntry):
        self.session.add(entry)
        self.session.flush()
        return entry
