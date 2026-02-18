import uuid
from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(20), default="user"
    )  # admin, user, readonly
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_key: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="owner")
    tags: Mapped[list["Tag"]] = relationship(back_populates="owner")

    def __repr__(self) -> str:
        return f"<User {self.username}>"


from app.models.document import Document  # noqa: E402
from app.models.tag import Tag  # noqa: E402
