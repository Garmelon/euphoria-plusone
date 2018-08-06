import asyncio
import sqlite3
import sys

import yaboli
from yaboli.utils import *

from plusone import PointsDB


async def add_points(db, room, points):
	for (nick, amount) in points:
		#print(f"&{room}: {mention(nick, ping=False)} + {amount}")
		await db.add_points(room, nick, amount)

def main(to_dbfile, from_dbfile, room):
	from_db = sqlite3.connect(from_dbfile)
	res = from_db.execute("SELECT nick, points FROM Points")
	points = res.fetchall()

	to_db = PointsDB(to_dbfile)
	asyncio.get_event_loop().run_until_complete(add_points(to_db, room, points))

if __name__ == "__main__":
	if len(sys.argv) == 4:
		main(sys.argv[1], sys.argv[2], sys.argv[3])
	else:
		print("  USAGE:")
		print(f"{sys.argv[0]} <pointsdb> <old_pointsdb> <room>")
		exit(1)
