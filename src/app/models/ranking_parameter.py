from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RankingParameter(Base):
    __tablename__ = "ranking_parameters"
    __table_args__ = (
        UniqueConstraint("year", name="uq_ranking_parameters_year"),
        CheckConstraint("year BETWEEN 2000 AND 9999", name="ck_ranking_parameters_year"),
        CheckConstraint(
            "minimum_achievement_percent >= 0",
            name="ck_ranking_parameters_minimum_achievement",
        ),
        CheckConstraint(
            "billing_level_1_min >= 0 AND billing_level_1_min < billing_level_2_min "
            "AND billing_level_2_min < billing_level_3_min",
            name="ck_ranking_parameters_billing_levels",
        ),
        CheckConstraint(
            "acquisition_level_1_min >= 0 AND acquisition_level_1_min < acquisition_level_2_min "
            "AND acquisition_level_2_min < acquisition_level_3_min",
            name="ck_ranking_parameters_acquisition_levels",
        ),
        CheckConstraint(
            "billing_level_1_points >= 0 AND billing_level_2_points >= 0 "
            "AND billing_level_3_points >= 0 AND acquisition_level_1_points >= 0 "
            "AND acquisition_level_2_points >= 0 AND acquisition_level_3_points >= 0 "
            "AND zero_cancellation_points >= 0 AND positive_cancellation_points >= 0",
            name="ck_ranking_parameters_nonnegative_points",
        ),
        CheckConstraint(
            "first_place_award >= 0 AND second_place_award >= 0 AND third_place_award >= 0",
            name="ck_ranking_parameters_nonnegative_awards",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    minimum_achievement_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    billing_level_1_min: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    billing_level_1_points: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_level_2_min: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    billing_level_2_points: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_level_3_min: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    billing_level_3_points: Mapped[int] = mapped_column(Integer, nullable=False)
    acquisition_level_1_min: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    acquisition_level_1_points: Mapped[int] = mapped_column(Integer, nullable=False)
    acquisition_level_2_min: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    acquisition_level_2_points: Mapped[int] = mapped_column(Integer, nullable=False)
    acquisition_level_3_min: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    acquisition_level_3_points: Mapped[int] = mapped_column(Integer, nullable=False)
    zero_cancellation_points: Mapped[int] = mapped_column(Integer, nullable=False)
    positive_cancellation_points: Mapped[int] = mapped_column(Integer, nullable=False)
    first_place_award: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    second_place_award: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    third_place_award: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @classmethod
    def defaults_2026(cls) -> "RankingParameter":
        return cls(
            year=2026,
            minimum_achievement_percent=Decimal("100"),
            billing_level_1_min=Decimal("100"), billing_level_1_points=5,
            billing_level_2_min=Decimal("110"), billing_level_2_points=6,
            billing_level_3_min=Decimal("150"), billing_level_3_points=7,
            acquisition_level_1_min=Decimal("1"), acquisition_level_1_points=2,
            acquisition_level_2_min=Decimal("8"), acquisition_level_2_points=3,
            acquisition_level_3_min=Decimal("16"), acquisition_level_3_points=4,
            zero_cancellation_points=1, positive_cancellation_points=0,
            first_place_award=Decimal("3000.00"),
            second_place_award=Decimal("2000.00"),
            third_place_award=Decimal("1000.00"),
        )
