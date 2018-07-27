import asyncio
import re

import yaboli
from yaboli.utils import *
import database

# List of rooms kept in separate file, which is .gitignore'd
import join_rooms


class PointDB(database.Database):
	@database.Database.operation
	def initialize(conn):
		cur = conn.cursor()
		cur.execute((
			"CREATE TABLE IF NOT EXISTS Points ("
				"nick TEXT UNIQUE NOT NULL,"
				"points INTEGER"
			")"
		))
		conn.commit()

	@database.Database.operation
	def add_point(conn, nick):
		nick = mention_reduced(nick)
		cur = conn.cursor()

		cur.execute("INSERT OR IGNORE INTO Points (nick, points) VALUES (?, 0)", (nick,))
		cur.execute("UPDATE Points SET points=points+1 WHERE nick=?", (nick,))
		conn.commit()

	@database.Database.operation
	def points_of(conn, nick):
		nick = mention_reduced(nick)
		cur = conn.cursor()

		cur.execute("SELECT points FROM Points WHERE nick=?", (nick,))
		res = cur.fetchone()
		if res is not None:
			return res[0]
		else:
			return 0


PLUSONE_RE = r"(\+1|:\+1:|:bronze(!\?|\?!)?:)\s*(.*)"
MENTION_RE = r"((for|to)\s+)?@(\S+)"

class PlusOne(yaboli.Bot):
	"""
	Count +1s awarded to users by other users.
	"""

	async def created(self, room):
		room.pointsdb = PointDB(f"points-{room.roomname}.db")
		await room.pointsdb.initialize()

	async def send(self, room, message):
		ping_text = ":bronze!?:"
		short_help = "/me counts :+1:s"
		long_help = (
			"Counts +1/:+1:/:bronze:s: Simply reply \"+1\" to someone's message to award them a point.\n"
			"Alternatively, specify a person with: \"+1 [to|for] @person\"\n"
			"\n"
			"!points - show your own points\n"
			"!points <person1> [<person2> ...] - list other people's points\n"
			"\n"
			"Created by @Garmy using https://github.com/Garmelon/yaboli.\n"
		)
		await self.botrulez_ping_general(room, message, ping_text=ping_text)
		await self.botrulez_ping_specific(room, message, ping_text=ping_text)
		await self.botrulez_help_general(room, message, help_text=short_help)
		await self.botrulez_help_specific(room, message, help_text=long_help)
		await self.botrulez_uptime(room, message)
		await self.botrulez_kill(room, message)
		await self.botrulez_restart(room, message)

		await self.command_points(room, message)

		await self.trigger_plusone(room, message)

	forward = send

	@yaboli.command("points", specific=False, args=True)
	async def command_points(self, room, message, argstr):
		args = self.parse_args(argstr)
		if not args:
			points = await room.pointsdb.points_of(message.sender.nick)
			await room.send(
				f"You have {points} point{'s' if points != 1 else ''}.",
				message.mid
			)
		else:
			response = []
			for arg in args:
				if arg[:1] == "@":
					nick = arg[1:]
				else:
					nick = arg
				points = await room.pointsdb.points_of(nick)
				response.append(f"{mention(nick)} has {points} point{'' if points == 1 else 's'}.")
			await room.send("\n".join(response), message.mid)

	@yaboli.trigger(PLUSONE_RE)
	async def trigger_plusone(self, room, message, match):
		nick = None
		specific = re.match(MENTION_RE, match.group(3))

		if specific:
			nick = specific.group(3)
		elif message.parent:
			parent_message = await room.get_message(message.parent)
			nick = parent_message.sender.nick

		if nick is None:
			await room.send("You can't +1 nothing...", message.mid)
		elif similar(nick, message.sender.nick):
			await room.send("Don't +1 yourself, that's not how things work.", message.mid)
		else:
			await room.pointsdb.add_point(nick)
			await room.send(f"Point for user {mention(nick)} registered.", message.mid)

def main():
	bot = PlusOne("PlusOne")
	join_rooms.join_rooms(bot)
	asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
	main()
