from datetime import datetime

from sqlalchemy import DateTime, SmallInteger, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SitemapURL(Base):
    __tablename__ = "sitemap_urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    body: Mapped[str | None] = mapped_column(Text)
    response_code: Mapped[int | None] = mapped_column(SmallInteger)
    date_added: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    date_updated: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
