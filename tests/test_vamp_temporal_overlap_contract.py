import sqlite3


def select_tasks(connection, months):
    overlap = " OR ".join(
        "(substr(window_start,1,7) <= ? AND substr(window_end,1,7) >= ?)"
        for _ in months
    )
    return [
        row[0]
        for row in connection.execute(
            f"SELECT task_id FROM tasks WHERE ({overlap}) ORDER BY task_id",
            tuple(value for month in months for value in (month, month)),
        )
    ]


def test_review_month_includes_active_long_running_objective():
    with sqlite3.connect(":memory:") as connection:
        connection.execute(
            "CREATE TABLE tasks(task_id TEXT, window_start TEXT, window_end TEXT)"
        )
        connection.executemany(
            "INSERT INTO tasks VALUES(?,?,?)",
            [
                ("ACTIVE", "2026-01-01", "2026-08-31"),
                ("EXPIRED", "2026-01-01", "2026-07-31"),
                ("FUTURE", "2026-09-01", "2026-12-31"),
            ],
        )
        assert select_tasks(connection, ["2026-08"]) == ["ACTIVE"]


def test_noncontiguous_review_months_do_not_include_intervening_only_tasks():
    with sqlite3.connect(":memory:") as connection:
        connection.execute(
            "CREATE TABLE tasks(task_id TEXT, window_start TEXT, window_end TEXT)"
        )
        connection.executemany(
            "INSERT INTO tasks VALUES(?,?,?)",
            [
                ("JAN", "2026-01-01", "2026-01-31"),
                ("FEB_ONLY", "2026-02-01", "2026-02-28"),
                ("MAR", "2026-03-01", "2026-03-31"),
            ],
        )
        assert select_tasks(connection, ["2026-01", "2026-03"]) == [
            "JAN", "MAR"
        ]
