from sqlmodel import Session


def test_database_is_test_database(db: Session) -> None:
    current_database = (
        db.connection().exec_driver_sql("SELECT current_database()").scalar_one()
    )
    assert current_database == "app_test"
