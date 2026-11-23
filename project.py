import csv
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile


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
    """Summarize matches in recording order, oldest first."""
    stats = {name: dict(wins=0, draws=0, losses=0, goals=0, form="", streak=0)
             for name in players}
    for goals, penalties in matches:
        winner = get_winner(players, goals, penalties)
        for name, scored in zip(players, goals):
            if winner is None:
                result = "draws"
            elif winner == name:
                result = "wins"
            else:
                result = "losses"
            player = stats[name]
            player[result] += 1
            player["goals"] += scored
            player["form"] = (player["form"] + result[0].upper())[-5:]
            player["streak"] = player["streak"] + 1 if winner == name else 0
    return stats


def prepare_database(db):
    db.execute("PRAGMA foreign_keys = ON")
    with db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS rivalry
            (id INTEGER PRIMARY KEY, first TEXT NOT NULL, second TEXT NOT NULL)""")
        columns = {row[1] for row in db.execute("PRAGMA table_info(matches)")}
        legacy = bool(columns) and "rivalry_id" not in columns
        if legacy:
            db.execute("ALTER TABLE matches RENAME TO legacy_matches")
        db.execute("""CREATE TABLE IF NOT EXISTS matches
            (id INTEGER PRIMARY KEY, rivalry_id INTEGER NOT NULL REFERENCES rivalry(id),
             g1 INTEGER NOT NULL, g2 INTEGER NOT NULL, p1 INTEGER, p2 INTEGER)""")
        if legacy:
            # Earlier versions stored all results for the single rivalry with ID 1.
            db.execute("""INSERT INTO matches (id, rivalry_id, g1, g2, p1, p2)
                SELECT id, 1, g1, g2, p1, p2 FROM legacy_matches""")
            db.execute("DROP TABLE legacy_matches")
        db.execute("CREATE INDEX IF NOT EXISTS matches_by_rivalry ON matches(rivalry_id, id)")


def create_rivalry(db):
    while True:
        first = input("First player's name: ").strip()
        second = input("Second player's name: ").strip()
        if first and second and first.casefold() != second.casefold():
            break
        print("Use two distinct, nonempty player names.")
    pair = {first.casefold(), second.casefold()}
    with db:
        db.execute("BEGIN IMMEDIATE")
        for rivalry in db.execute("SELECT id, first, second FROM rivalry"):
            if {rivalry[1].casefold(), rivalry[2].casefold()} == pair:
                print("Opening the existing rivalry for these players.")
                return rivalry
        saved = db.execute("INSERT INTO rivalry (first, second) VALUES (?, ?)", (first, second))
        return saved.lastrowid, first, second


def choose_rivalry(db, current=None):
    rivalries = db.execute("SELECT id, first, second FROM rivalry ORDER BY id").fetchall()
    if not rivalries:
        return create_rivalry(db)
    if current is None and len(rivalries) == 1:
        return rivalries[0]
    for rivalry_id, first, second in rivalries:
        print(f"{rivalry_id}. {first} vs {second}")
    default = current or rivalries[0]
    while True:
        choice = input(f"Rivalry ID, N for new, or Enter for #{default[0]}: ").strip()
        if not choice:
            return default
        if choice.lower() == "n":
            return create_rivalry(db)
        for rivalry in rivalries:
            if choice == str(rivalry[0]):
                return rivalry
        print("Choose a listed rivalry ID or N.")


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


def record_match(db, rivalry_id, players):
    result = read_result(players)
    with db:
        db.execute("INSERT INTO matches (rivalry_id, g1, g2, p1, p2) VALUES (?, ?, ?, ?, ?)",
                   (rivalry_id, *result))
    print("Match saved.")


def correct_match(db, rivalry_id, players):
    match_id = input("Match ID from history (Enter to cancel): ").strip()
    if not match_id:
        return
    original = db.execute(
        "SELECT g1, g2, p1, p2 FROM matches WHERE id = ? AND rivalry_id = ?", (match_id, rivalry_id)
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
            WHERE id = ? AND rivalry_id = ? AND g1 = ? AND g2 = ? AND p1 IS ? AND p2 IS ?
        """, (*updated, match_id, rivalry_id, *original))
    if changed.rowcount:
        print("Correction saved.")
    else:
        print("The match changed during editing. Check its latest result and try again.")


def export_history(rivalry_id, players, rows):
    """Write a separate CSV snapshot each time, in the history display order."""
    folder = DATABASE.parent / "exports"
    folder.mkdir(exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=folder,
                           prefix=f"rivalry-{rivalry_id}-", suffix=".csv",
                           delete=False) as output:
        path = Path(output.name)
        try:
            writer = csv.writer(output)
            writer.writerow(("match_id", "player_1", "player_2", "goals_1", "goals_2",
                             "penalties_1", "penalties_2", "outcome_for_player_1"))
            for match_id, g1, g2, p1, p2 in rows:
                winner = get_winner(players, (g1, g2), None if p1 is None else (p1, p2))
                outcomes = {None: "draw", players[0]: "win", players[1]: "loss"}
                outcome = outcomes[winner]
                writer.writerow((match_id, *players, g1, g2, p1, p2, outcome))
            output.flush()
        except BaseException:
            output.close()
            path.unlink(missing_ok=True)
            raise
    return path


def main():
    with closing(sqlite3.connect(DATABASE)) as db:
        prepare_database(db)
        print("FIFA Rivalry Tracker")
        rivalry = choose_rivalry(db)
        while True:
            rivalry_id, *players = rivalry
            print(f"\nRivalry: {players[0]} vs {players[1]}")
            print("\n1. Record a match\n2. Match history\n3. Rivalry stats\n4. Quit\n5. Correct a result")
            print("6. Switch or create a rivalry")
            print("7. Export match history to CSV")
            choice = input("Choose an option: ").strip()
            if choice == "4":
                return
            if choice == "1":
                record_match(db, rivalry_id, players)
            elif choice == "5":
                correct_match(db, rivalry_id, players)
            elif choice == "6":
                rivalry = choose_rivalry(db, rivalry)
            elif choice in {"2", "3", "7"}:
                rows = db.execute("""SELECT id, g1, g2, p1, p2 FROM matches
                    WHERE rivalry_id = ? ORDER BY id DESC""", (rivalry_id,)).fetchall()
                if not rows:
                    print("No matches recorded yet.")
                elif choice == "7":
                    try:
                        path = export_history(rivalry_id, players, rows)
                        print(f"Exported {len(rows)} match(es) to {path}")
                    except OSError as error:
                        print(f"Could not export match history: {error}")
                elif choice == "2":
                    for match_id, *result in rows:
                        print(f"#{match_id}: {format_result(players, result)}")
                else:
                    matches = ((row[1:3], None if row[3] is None else row[3:])
                               for row in reversed(rows))
                    for name, stats in summarize_rivalry(players, matches).items():
                        print(f"{name}: {stats['wins']} W, {stats['draws']} D, "
                              f"{stats['losses']} L, {stats['goals']} goals")
                        print(f"  Last five (oldest first): {' '.join(stats['form'])}")
                        print(f"  Current winning streak: {stats['streak']}")
            else:
                print("Choose an option from 1 to 7.")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")
