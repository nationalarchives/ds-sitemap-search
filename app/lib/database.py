import os

from sqlalchemy import URL, create_engine, inspect, text

from app.models import Base

engine = create_engine(
    URL.create(
        "postgresql+psycopg",
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        username=os.environ.get("DB_USERNAME"),
        password=os.environ.get("DB_PASSWORD"),
    ),
    connect_args={"connect_timeout": 3},
    pool_pre_ping=True,
)


def create_database(drop_table=False):
    with engine.begin() as connection:
        if drop_table:
            Base.metadata.drop_all(connection)
        Base.metadata.create_all(connection)
        columns = inspect(connection).get_columns("sitemap_urls")
        if not any(column["name"] == "response_code" for column in columns):
            connection.execute(
                text("ALTER TABLE sitemap_urls ADD COLUMN response_code SMALLINT")
            )
