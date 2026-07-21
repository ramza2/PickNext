import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base


class CategoryType(str, enum.Enum):
    MEDIA = "MEDIA"
    BOOK = "BOOK"
    FOOD = "FOOD"
    GENERAL = "GENERAL"


class ItemStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"


class StatusFilter(str, enum.Enum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"
    ALL = "ALL"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    categories: Mapped[list["Category"]] = relationship(back_populates="user")
    collections: Mapped[list["Collection"]] = relationship(back_populates="user")
    items: Mapped[list["Item"]] = relationship(back_populates="user")
    recommendation_histories: Mapped[list["RecommendationHistory"]] = relationship(
        back_populates="user"
    )


class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_categories_user_id_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_type: Mapped[CategoryType] = mapped_column(
        Enum(CategoryType, name="category_type", native_enum=True),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    user: Mapped[User] = relationship(back_populates="categories")
    items: Mapped[list["Item"]] = relationship(back_populates="category")
    recommendation_histories: Mapped[list["RecommendationHistory"]] = relationship(
        back_populates="category"
    )


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_collections_user_id_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    user: Mapped[User] = relationship(back_populates="collections")
    items: Mapped[list["Item"]] = relationship(back_populates="collection")
    recommendation_histories: Mapped[list["RecommendationHistory"]] = relationship(
        back_populates="collection"
    )


class Item(Base, TimestampMixin):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("rating >= 0 AND rating <= 5", name="ck_items_rating_range"),
        CheckConstraint(
            "(rating * 2) = floor(rating * 2)",
            name="ck_items_rating_half_step",
        ),
        Index("ix_items_user_id_category_id", "user_id", "category_id"),
        Index("ix_items_user_id_status", "user_id", "status"),
        Index(
            "ix_items_active",
            "user_id",
            "category_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, name="item_status", native_enum=True),
        nullable=False,
    )
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    progress_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="items")
    category: Mapped[Category] = relationship(back_populates="items")
    collection: Mapped[Collection | None] = relationship(back_populates="items")
    recommendation_history_items: Mapped[list["RecommendationHistoryItem"]] = relationship(
        back_populates="item"
    )

    @validates("rating")
    def validate_rating(self, _key: str, value: Decimal | float | int | str) -> Decimal:
        rating = Decimal(str(value))
        if rating < Decimal("0") or rating > Decimal("5"):
            raise ValueError("rating must be between 0.0 and 5.0")
        if (rating * 2) != (rating * 2).to_integral_value():
            raise ValueError("rating must be in 0.5 increments")
        return rating


class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status_filter: Mapped[StatusFilter] = mapped_column(
        Enum(StatusFilter, name="status_filter", native_enum=True),
        nullable=False,
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="recommendation_histories")
    category: Mapped[Category] = relationship(back_populates="recommendation_histories")
    collection: Mapped[Collection | None] = relationship(back_populates="recommendation_histories")
    items: Mapped[list["RecommendationHistoryItem"]] = relationship(
        back_populates="recommendation_history",
        cascade="all, delete-orphan",
    )


class RecommendationHistoryItem(Base):
    __tablename__ = "recommendation_history_items"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_history_id",
            "item_id",
            name="uq_recommendation_history_items_history_item",
        ),
        Index(
            "ix_recommendation_history_items_history_sort",
            "recommendation_history_id",
            "sort_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    recommendation_history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    status_at_selection: Mapped[ItemStatus] = mapped_column(
        Enum(
            ItemStatus,
            name="item_status",
            native_enum=True,
            create_constraint=False,
            create_type=False,
        ),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    recommendation_history: Mapped[RecommendationHistory] = relationship(back_populates="items")
    item: Mapped[Item] = relationship(back_populates="recommendation_history_items")


class LegacyImportRunStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class LegacyImportDisposition(str, enum.Enum):
    IMPORTED = "IMPORTED"
    SKIPPED_MISSING_CATEGORY = "SKIPPED_MISSING_CATEGORY"
    SKIPPED_DUPLICATE_TITLE = "SKIPPED_DUPLICATE_TITLE"


class LegacyImportRun(Base):
    __tablename__ = "legacy_import_runs"
    __table_args__ = (
        Index(
            "uq_legacy_import_runs_user_sha_success",
            "user_id",
            "source_sha256",
            unique=True,
            postgresql_where=text("status = 'SUCCESS'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[LegacyImportRunStatus] = mapped_column(
        Enum(LegacyImportRunStatus, name="legacy_import_run_status", native_enum=True),
        nullable=False,
    )

    user: Mapped[User] = relationship()
    items: Mapped[list["LegacyImportItem"]] = relationship(
        back_populates="import_run",
        cascade="all, delete-orphan",
    )
    collections: Mapped[list["LegacyImportCollection"]] = relationship(
        back_populates="import_run",
        cascade="all, delete-orphan",
    )


class LegacyImportItem(Base):
    __tablename__ = "legacy_import_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legacy_import_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[LegacyImportDisposition] = mapped_column(
        Enum(LegacyImportDisposition, name="legacy_import_disposition", native_enum=True),
        nullable=False,
    )

    import_run: Mapped[LegacyImportRun] = relationship(back_populates="items")
    item: Mapped[Item | None] = relationship()


class LegacyImportCollection(Base):
    __tablename__ = "legacy_import_collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legacy_import_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_name: Mapped[str] = mapped_column(String(200), nullable=False)

    import_run: Mapped[LegacyImportRun] = relationship(back_populates="collections")
    collection: Mapped[Collection] = relationship()
