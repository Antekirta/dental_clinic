from sqlalchemy import text

from app.db.base import Base
import app.db.models  # noqa: F401
from app.db.session import SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        table_names = [
            table.name
            for table in reversed(Base.metadata.sorted_tables)
            if table.schema in (None, "public")
        ]

        if not table_names:
            print("No mapped application tables found.")
            return

        joined = ", ".join(f'"{name}"' for name in table_names)
        session.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"Cleared tables: {', '.join(table_names)}")


if __name__ == "__main__":
    main()
