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


def read_result(players):
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
    return (*goals, *(penalties or (None, None)))


def format_result(players, result):
    first, second, pens_first, pens_second = result
    score = f"{players[0]} {first}-{second} {players[1]}"
    if pens_first is not None:
        score += f" ({pens_first}-{pens_second} on pens)"
    return score


def record_match(db, players):
    result = read_result(players)
    with db:
        db.execute("INSERT INTO matches (g1, g2, p1, p2) VALUES (?, ?, ?, ?)", result)
    print("Match saved.")


def correct_match(db, players):
    match_id = input("Match ID from history (Enter to cancel): ").strip()
    if not match_id:
        return
    original = db.execute(
        "SELECT g1, g2, p1, p2 FROM matches WHERE id = ?", (match_id,)
    ).fetchone()
    if original is None:
        print("Match ID not found. Choose Match history to see available IDs.")
        return

    print(f"Current #{match_id}: {format_result(players, original)}")
    updated = read_result(players)
    print(f"Proposed #{match_id}: {format_result(players, updated)}")
    if input("Save correction? [y/N] ").strip().lower() not in {"y", "yes"}:
        print("Correction cancelled.")
        return

    with db:
        changed = db.execute("""
            UPDATE matches SET g1 = ?, g2 = ?, p1 = ?, p2 = ?
            WHERE id = ? AND g1 = ? AND g2 = ? AND p1 IS ? AND p2 IS ?
        """, (*updated, match_id, *original))
    if changed.rowcount:
        print("Correction saved.")
    else:
        print("The match changed during editing. Check its latest result and try again.")


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
            print("\n1. Record a match\n2. Match history\n3. Rivalry stats\n4. Quit\n5. Correct a result")
            choice = input("Choose an option: ").strip()
            if choice == "4":
                return
            if choice == "1":
                record_match(db, players)
            elif choice == "5":
                correct_match(db, players)
            elif choice in {"2", "3"}:
                rows = db.execute("SELECT id, g1, g2, p1, p2 FROM matches ORDER BY id DESC").fetchall()
                if not rows:
                    print("No matches recorded yet.")
                elif choice == "2":
                    for match_id, *result in rows:
                        print(f"#{match_id}: {format_result(players, result)}")
                else:
                    matches = [(row[1:3], None if row[3] is None else row[3:]) for row in rows]
                    for name, stats in summarize_rivalry(players, matches).items():
                        print(f"{name}: {stats['wins']} W, {stats['draws']} D, "
                              f"{stats['losses']} L, {stats['goals']} goals")
            else:
                print("Choose an option from 1 to 5.")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")
