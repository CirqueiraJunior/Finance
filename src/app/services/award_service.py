"""Valores oficiais da premiação trimestral Acelera Goiás."""

from decimal import Decimal


class AwardService:
    AWARDS = {
        1: Decimal("3000.00"),
        2: Decimal("2000.00"),
        3: Decimal("1000.00"),
    }

    @classmethod
    def value_for_position(cls, position: int | None) -> Decimal | None:
        return cls.AWARDS.get(position)
