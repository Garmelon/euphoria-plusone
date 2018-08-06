import asyncio
import configparser
import logging
import re

import yaboli
from yaboli.utils import *


logger = logging.getLogger("plusone")

class PointsDB(yaboli.Database):
	def initialize(self, db):
		with db:
			db.execute((
				"CREATE TABLE IF NOT EXISTS points ("
					"normalized_nick TEXT PRIMARY KEY, "
					"nick TEXT NOT NULL, "
					"room TEXT NOT NULL, "
					"points INTEGER NOT NULL"
				")"
			))

	@yaboli.operation
	def add_points(self, db, room, nick, points):
		normalized_nick = normalize(nick)
		with db:
			db.execute(
				"INSERT OR IGNORE INTO points VALUES (?,?,?,0)",
				(normalized_nick, nick, room)
			)
			db.execute((
				"UPDATE points "
				"SET points=points+?, nick=? "
				"WHERE normalized_nick=? AND room=?"
			), (points, nick, normalized_nick, room))

	@yaboli.operation
	def points_of(self, db, room, nick):
		normalized_nick = normalize(nick)
		res = db.execute((
			"SELECT points FROM points "
			"WHERE normalized_nick=? AND room=?"
		), (normalized_nick, room))
		points = res.fetchone()
		return points[0] if points else 0

class PlusOne:
	SHORT_DESCRIPTION = "counts :+1:s"
	DESCRIPTION = (
		"'plusone' counts +1/:+1:/:bronze:s:"
		" Simply reply '+1' to someone's message to give them a point.\n"
		" Alternatively, specify a person with: '+1 [to] @person'.\n"
	)
	COMMANDS = (
		"!points - show your own points\n"
		"!points <nick> [<nick> ...]  - list other people's points\n"
	)
	AUTHOR = "Created by @Garmy using github.com/Garmelon/yaboli\n"

	PLUSONE_RE = r"\s*(\+1|:\+1:|:bronze(!\?|\?!)?:)\s*(.*)"
	MENTION_RE = r"(to\s+@?|@)(\S+)"

	def __init__(self, dbfile):
		self.db = PointsDB(dbfile)

	@yaboli.command("points")
	async def command_points(self, room, message, argstr):
		args = yaboli.Bot.parse_args(argstr)
		if args:
			lines = []
			for nick in args:
				if nick[0] == "@": # a bit hacky, requires you to mention nicks starting with '@'
					nick = nick[1:]

				points = await self.db.points_of(room.roomname, nick)
				line = f"{mention(nick, ping=False)} has {points} point{'' if points == 1 else 's'}."
				lines.append(line)

			text = "\n".join(lines)
			await room.send(text, message.mid)

		else: # your own points
			points = await self.db.points_of(room.roomname, message.sender.nick)
			text = f"You have {points} point{'' if points == 1 else 's'}."
			await room.send(text, message.mid)

	@yaboli.trigger(PLUSONE_RE, flags=re.IGNORECASE)
	async def trigger_plusone(self, room, message, match):
		specific = re.match(self.MENTION_RE, match.group(3))

		nick = None
		if specific:
			nick = specific.group(2)
		elif message.parent:
			parent_message = await room.get_message(message.parent)
			nick = parent_message.sender.nick

		if nick is None:
			text = "You can't +1 nothing..."
		elif similar(nick, message.sender.nick):
			text = "There's no such thing as free points on the internet."
		else:
			await self.db.add_points(room.roomname, nick, 1)
			text = f"Point for user {mention(nick, ping=False)} registered."
		await room.send(text, message.mid)

class PlusOneBot(yaboli.Bot):
	PING_TEXT = ":bronze?!:"
	SHORT_HELP = PlusOne.SHORT_DESCRIPTION
	LONG_HELP = PlusOne.DESCRIPTION + PlusOne.COMMANDS + PlusOne.AUTHOR

	def __init__(self, nick, dbfile, cookiefile=None):
		super().__init__(nick, cookiefile=cookiefile)
		self.plusone = PlusOne(dbfile)

	async def on_send(self, room, message):
		await super().on_send(room, message)

		await self.plusone.trigger_plusone(room, message)

	async def on_command_specific(self, room, message, command, nick, argstr):
		if similar(nick, room.session.nick) and not argstr:
			await self.botrulez_ping(room, message, command, text=self.PING_TEXT)
			await self.botrulez_help(room, message, command, text=self.LONG_HELP)
			await self.botrulez_uptime(room, message, command)
			await self.botrulez_kill(room, message, command, text="-1")
			await self.botrulez_restart(room, message, command, text="∓1")

	async def on_command_general(self, room, message, command, argstr):
		if not argstr:
			await self.botrulez_ping(room, message, command, text=self.PING_TEXT)
			await self.botrulez_help(room, message, command, text=self.SHORT_HELP)

		await self.plusone.command_points(room, message, command, argstr)

def main(configfile):
	logging.basicConfig(level=logging.INFO)

	config = configparser.ConfigParser(allow_no_value=True)
	config.read(configfile)

	nick = config.get("general", "nick")
	cookiefile = config.get("general", "cookiefile", fallback=None)
	dbfile = config.get("general", "dbfile", fallback=None)
	bot = PlusOneBot(nick, dbfile, cookiefile=cookiefile)

	for room, password in config.items("rooms"):
		if not password:
			password = None
		bot.join_room(room, password=password)

	asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
	main("plusone.conf")
