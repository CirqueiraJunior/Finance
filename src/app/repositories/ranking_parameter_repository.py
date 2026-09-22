from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ranking_parameter import RankingParameter
from app.repositories.base import BaseRepository


class RankingParameterRepository(BaseRepository[RankingParameter]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_year(self, year: int) -> RankingParameter | None:
        return self.session.scalar(
            select(RankingParameter).where(RankingParameter.year == year)
        )
