import asyncio
import configparser
import logging
import re

import yaboli
from yaboli.utils import *


# Turn all debugging on
asyncio.get_event_loop().set_debug(True)
#logging.getLogger("asyncio").setLevel(logging.INFO)
#logging.getLogger("yaboli").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class PointDB(yaboli.Database):
	def initialize(self, db): # called automatically
		db.execute((
			"CREATE TABLE IF NOT EXISTS Points ( "
				"nick TEXT UNIQUE NOT NULL, "
				"points INTEGER "
			")"
		))
		db.commit()

	@yaboli.operation
	def add_point(self, db, nick):
		nick = normalize(nick)

		cur = db.cursor()
		cur.execute("INSERT OR IGNORE INTO Points (nick, points) VALUES (?, 0)", (nick,))
		cur.execute("UPDATE Points SET points=points+1 WHERE nick=?", (nick,))
		db.commit()

	@yaboli.operation
	def points_of(self, db, nick):
		nick = normalize(nick)

		cur = db.execute("SELECT points FROM Points WHERE nick=?", (nick,))
		res = cur.fetchone()
		return res[0] if res is not None else 0


PLUSONE_RE = r"(\+1|:\+1:|:bronze(!\?|\?!)?:)\s*(.*)"
MENTION_RE = r"((for|to)\s+|@)(\S+)"

class PlusOne(yaboli.Bot):
	"""
	Count +1s awarded to users by other users.
	"""

	PING_TEXT = ":bronze!?"
	SHORT_HELP = "/me counts :+1:s"
	LONG_HELP = (
		"Counts +1/:+1:/:bronze:s: Simply reply \"+1\" to someone's message to award them a point.\n"
		"Alternatively, specify a person with: \"+1 [to|for] @person\"\n"
		"\n"
		"!points - show your own points\n"
		"!points <person1> [<person2> ...] - list other people's points\n"
		"\n"
		"Created by @Garmy using https://github.com/Garmelon/yaboli.\n"
	)

	async def on_created(self, room):
		room.pointdb = PointDB(f"points-{room.roomname}.db")

	async def on_command_specific(self, room, message, command, nick, argstr):
		if similar(nick, room.session.nick) and not argstr:
			await self.botrulez_ping(room, message, command, text=self.PING_TEXT)
			await self.botrulez_help(room, message, command, text=self.LONG_HELP)
			await self.botrulez_uptime(room, message, command)
			await self.botrulez_kill(room, message, command)
			await self.botrulez_restart(room, message, command)


	async def on_command_general(self, room, message, command, argstr):
		if not argstr:
			await self.botrulez_ping(room, message, command, text=self.PING_TEXT)
			await self.botrulez_help(room, message, command, text=self.SHORT_HELP)

		await self.command_points(room, message, command, argstr)

	async def on_send(self, room, message):
		await super().on_send(room, message)
		await self.trigger_plusone(room, message)

	@yaboli.command("points")
	async def command_points(self, room, message, argstr):
		args = self.parse_args(argstr)
		if not args:
			points = await room.pointdb.points_of(message.sender.nick)
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
				points = await room.pointdb.points_of(nick)
				response.append(f"{mention(nick)} has {points} point{'' if points == 1 else 's'}.")
			await room.send("\n".join(response), message.mid)

	@yaboli.trigger(PLUSONE_RE)
	async def trigger_plusone(self, room, message, match):
		nick = None
		specific = re.match(MENTION_RE, match.group(3))

		if specific:
			nick = specific.group(3)
			if nick[0] == "@":
				nick = nick[1:]
		elif message.parent:
			parent_message = await room.get_message(message.parent)
			nick = parent_message.sender.nick

		if nick is None:
			await room.send("You can't +1 nothing...", message.mid)
		elif similar(nick, message.sender.nick):
			await room.send("Don't +1 yourself, that's not how things work.", message.mid)
		else:
			await room.pointdb.add_point(nick)
			await room.send(f"Point for user {mention(nick)} registered.", message.mid)

def main(configfile):
	config = configparser.ConfigParser(allow_no_value=True)
	config.read(configfile)

	nick = config.get("general", "nick")
	cookiefile = config.get("general", "cookiefile", fallback=None)
	bot = PlusOne(nick, cookiefile=cookiefile)

	for room, password in config.items("rooms"):
		if not password:
			password = None
		bot.join_room(room, password=password)

	asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
	main("plusone.conf")
