from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.boe_entity_total import BOEEntityTotal
from app.models.boe_import import BOEImport
from app.models.boe_import_issue import BOEImportIssue
from app.repositories.base import BaseRepository


class BOERepository(BaseRepository[BOEImport]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_import_by_hash(self, file_hash: str) -> BOEImport | None:
        return self.session.scalar(
            select(BOEImport).where(BOEImport.hash_arquivo == file_hash)
        )

    def get_import_by_period(self, year: int, month: int) -> BOEImport | None:
        return self.session.scalar(
            select(BOEImport).where(
                BOEImport.periodo_ano == year,
                BOEImport.periodo_mes == month,
            )
        )

    def add_import(self, boe_import: BOEImport) -> BOEImport:
        self.session.add(boe_import)
        self.session.flush()
        return boe_import

    def add_entity_total(self, total: BOEEntityTotal) -> BOEEntityTotal:
        self.session.add(total)
        self.session.flush()
        return total

    def add_issue(self, issue: BOEImportIssue) -> BOEImportIssue:
        self.session.add(issue)
        self.session.flush()
        return issue

    def list_imports(self) -> list[BOEImport]:
        statement = select(BOEImport).order_by(
            BOEImport.periodo_ano.desc(),
            BOEImport.periodo_mes.desc(),
            BOEImport.id.desc(),
        )
        return list(self.session.scalars(statement))

    def get_import(self, import_id: int) -> BOEImport | None:
        statement = (
            select(BOEImport)
            .options(
                selectinload(BOEImport.entity_totals).selectinload(
                    BOEEntityTotal.entity
                ),
                selectinload(BOEImport.issues),
            )
            .where(BOEImport.id == import_id)
        )
        return self.session.scalar(statement)

    def list_totals_by_import(self, import_id: int) -> list[BOEEntityTotal]:
        statement = (
            select(BOEEntityTotal)
            .where(BOEEntityTotal.boe_import_id == import_id)
            .order_by(BOEEntityTotal.codigo_entidade_origem)
        )
        return list(self.session.scalars(statement))

    def list_operational_totals(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        entity_id: int | None = None,
    ) -> list[tuple[BOEEntityTotal, BOEImport]]:
        start_period = start_year * 100 + start_month
        end_period = end_year * 100 + end_month
        period = BOEImport.periodo_ano * 100 + BOEImport.periodo_mes
        statement = (
            select(BOEEntityTotal, BOEImport)
            .join(BOEImport, BOEImport.id == BOEEntityTotal.boe_import_id)
            .options(selectinload(BOEEntityTotal.entity))
            .where(
                BOEImport.status == "imported",
                period >= start_period,
                period <= end_period,
                BOEEntityTotal.codigo_entidade_origem != 7500,
            )
            .order_by(
                BOEImport.periodo_ano,
                BOEImport.periodo_mes,
                BOEEntityTotal.codigo_entidade_origem,
            )
        )
        if entity_id is not None:
            statement = statement.where(BOEEntityTotal.entity_id == entity_id)
        return list(self.session.execute(statement).tuples())
