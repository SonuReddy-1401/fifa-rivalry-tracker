import sqlite3
from contextlib import closing
from pathlib import Path


DATABASE = Path(__file__).with_name("rivalry.sqlite3")


def validate_score(goals, penalties=None):
    """Raise ValueError if the score cannot represent a finished match."""
    for pair in (goals,) if penalties is None else (goals, penalties):
        if len(pair) != 2 or any(type(n) is not int or n < 0 for n in pair):
            raise ValueError("Enter two non-negative whole numbers.")
    if penalties is not None:
        if goals[0] != goals[1]:
            raise ValueError("Only a tied match can go to penalties.")
        if penalties[0] == penalties[1]:
            raise ValueError("A finished shootout must have a winner.")


def get_winner(players, goals, penalties=None):
    validate_score(goals, penalties)
    first, second = penalties if penalties is not None else goals
    if first == second:
        return None
    return players[0] if first > second else players[1]


def summarize_rivalry(players, matches):
    stats = {name: dict(wins=0, draws=0, losses=0, goals=0) for name in players}
    for goals, penalties in matches:
        winner = get_winner(players, goals, penalties)
        for name, scored in zip(players, goals):
            if winner is None:
                result = "draws"
            elif winner == name:
                result = "wins"
            else:
                result = "losses"
            stats[name][result] += 1
            stats[name]["goals"] += scored
    return stats


def load_players(db):
    row = db.execute("SELECT first, second FROM rivalry WHERE id = 1").fetchone()
    if row:
        return row
    while True:
        first = input("First player's name: ").strip()
        second = input("Second player's name: ").strip()
        if first and second and first.casefold() != second.casefold():
            with db:
                db.execute("INSERT OR IGNORE INTO rivalry VALUES (1, ?, ?)", (first, second))
            return db.execute("SELECT first, second FROM rivalry WHERE id = 1").fetchone()
        print("Use two distinct, nonempty player names.")


def read_pair(prompt, optional=False):
    while True:
        raw = input(prompt).strip()
        if optional and not raw:
            return None
        try:
            score = tuple(int(value) for value in raw.split("-"))
            validate_score(score)
            if any(n > 2**63 - 1 for n in score):
                raise ValueError
            return score
        except ValueError:
            print("Enter two whole numbers like 2-1.")


def record_match(db, players):
    print(f"Score order: {players[0]} - {players[1]}")
    goals = read_pair("Match score (excluding penalties): ")
    penalties = None
    if goals[0] == goals[1]:
        while True:
            penalties = read_pair("Shootout score (press Enter for a draw): ", optional=True)
            try:
                validate_score(goals, penalties)
                break
            except ValueError as error:
                print(error)
    with db:
        db.execute("INSERT INTO matches (g1, g2, p1, p2) VALUES (?, ?, ?, ?)",
                   (*goals, *(penalties or (None, None))))
    print("Match saved.")


def main():
    with closing(sqlite3.connect(DATABASE)) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS rivalry
                (id INTEGER PRIMARY KEY, first TEXT NOT NULL, second TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS matches
                (id INTEGER PRIMARY KEY, g1 INTEGER NOT NULL, g2 INTEGER NOT NULL,
                 p1 INTEGER, p2 INTEGER);
        """)
        print("FIFA Rivalry Tracker")
        players = load_players(db)
        while True:
            print("\n1. Record a match\n2. Match history\n3. Rivalry stats\n4. Quit")
            choice = input("Choose an option: ").strip()
            if choice == "4":
                return
            if choice == "1":
                record_match(db, players)
            elif choice in {"2", "3"}:
                rows = db.execute("SELECT g1, g2, p1, p2 FROM matches ORDER BY id DESC")
                matches = [(row[:2], None if row[2] is None else row[2:]) for row in rows]
                if not matches:
                    print("No matches recorded yet.")
                elif choice == "2":
                    for goals, pens in matches:
                        suffix = f" ({pens[0]}-{pens[1]} on pens)" if pens else ""
                        print(f"{players[0]} {goals[0]}-{goals[1]} {players[1]}{suffix}")
                else:
                    for name, stats in summarize_rivalry(players, matches).items():
                        print(f"{name}: {stats['wins']} W, {stats['draws']} D, "
                              f"{stats['losses']} L, {stats['goals']} goals")
            else:
                print("Choose 1, 2, 3, or 4.")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")
