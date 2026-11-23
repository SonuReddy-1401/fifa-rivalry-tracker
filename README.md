# FIFA Rivalry Tracker

**Video demo** — Link pending recording.

## Description

FIFA Rivalry Tracker is a Python terminal program for friends who play FIFA together and want to keep a head-to-head record across sessions. Each rivalry belongs to two players. If Alex switches from Liverpool to Real Madrid halfway through the evening, the next result still counts toward Alex’s record against Sam. Games against another friend belong to a separate rivalry.

## Play your first rivalry

From the project folder, run:

```sh
python project.py
```

Enter both player names when prompted. Choose **1. Record a match** and enter a score such as `2-1`. The tracker shows the player order before asking for the score. For a tied match, press Enter to record a draw or enter the shootout score. Choose **2. Match history** to see the newest result first, along with the ID you can use to correct it later.

Suppose Alex and Sam draw 2–2 and Sam wins the shootout 5–4. With Alex listed first, enter `2-2` and then `4-5`. Sam earns one win and both players earn two goals. Under **3. Rivalry stats**, Sam’s form begins with a W. If they draw the next match, Sam’s form reads W D and the current winning streak drops to zero. Form shows up to five matches, oldest first, while the streak can extend beyond five.

## Correct, switch, and export

Choose **5. Correct a result** and enter its match ID. Review the current and proposed scores, then enter `y` to save or press Enter to cancel. A correction keeps the original position in history. The tracker calculates standings from the saved scores each time you view them, so correcting a match also updates the goal totals, recent form, and streaks.

Use **6. Switch or create a rivalry** when another friend joins. Entering the same pair in reverse order reopens their existing rivalry with its original score order. Use **4. Quit** to end the session. On a later launch, the tracker offers a choice if you have more than one rivalry.

Choose **7. Export match history to CSV** for a snapshot of the selected pair. The program prints the file path and saves each export separately in the `exports` folder beside the database. Rows follow the same newest-first order as match history. Each row includes the match ID, both names, match goals, shootout scores where applicable, and the outcome from the first player’s perspective. Blank shootout fields mean the match ended without penalties.

## Files and tests

`project.py` contains the menu, scoring rules, database access, and export code. SQLite saves the rivalry and match records together in `rivalry.sqlite3` beside the script. A match ID stays stable across corrections and exports. When opening a database from the original single-rivalry version, the tracker assigns those matches to the original pair.

`test_project.py` checks scoring rules and exercises the terminal workflow using temporary databases. `requirements.txt` lists pytest, the test dependency. The tracker itself runs with Python’s standard library. To install the test dependency and run the suite:

```sh
python -m pip install -r requirements.txt
python -m pytest -q
```
