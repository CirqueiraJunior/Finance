"""Valores oficiais da premiação trimestral Acelera Goiás."""

from decimal import Decimal

from app.models.ranking_parameter import RankingParameter


class AwardService:
    AWARDS = {
        1: Decimal("3000.00"),
        2: Decimal("2000.00"),
        3: Decimal("1000.00"),
    }

    @classmethod
    def value_for_position(
        cls, position: int | None, parameters: RankingParameter | None = None,
    ) -> Decimal | None:
        if parameters is None:
            return cls.AWARDS.get(position)
        return {
            1: parameters.first_place_award,
            2: parameters.second_place_award,
            3: parameters.third_place_award,
        }.get(position)
