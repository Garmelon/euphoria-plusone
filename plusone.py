import asyncio
import logging
import re

import yaboli
from yaboli.utils import *
from join_rooms import join_rooms # List of rooms kept in separate file, which is .gitignore'd

# Turn all debugging on
asyncio.get_event_loop().set_debug(True)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("yaboli").setLevel(logging.DEBUG)


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
	def add_point(db, nick):
		nick = mention_reduced(nick)

		cur = db.cursor()
		cur.execute("INSERT OR IGNORE INTO Points (nick, points) VALUES (?, 0)", (nick,))
		cur.execute("UPDATE Points SET points=points+1 WHERE nick=?", (nick,))
		db.commit()

	@yaboli.operation
	def points_of(db, nick):
		nick = mention_reduced(nick)

		cur = db.execute("SELECT points FROM Points WHERE nick=?", (nick,))
		res = cur.fetchone()
		return res[0] if res is not None else 0


PLUSONE_RE = r"(\+1|:\+1:|:bronze(!\?|\?!)?:)\s*(.*)"
MENTION_RE = r"((for|to)\s+|@)(\S+)"

class PlusOne(yaboli.Bot):
	"""
	Count +1s awarded to users by other users.
	"""

	async def on_created(self, room):
		room.pointdb = PointDB(f"points-{room.roomname}.db")

	async def on_send(self, room, message):
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
		await self.botrulez_ping_general(room, message, text=ping_text)
		await self.botrulez_ping_specific(room, message, text=ping_text)
		await self.botrulez_help_general(room, message, text=short_help)
		await self.botrulez_help_specific(room, message, text=long_help)
		await self.botrulez_uptime(room, message)
		await self.botrulez_kill(room, message)
		await self.botrulez_restart(room, message)

		await self.command_points(room, message)

		await self.trigger_plusone(room, message)

	@yaboli.command("points", specific=False, args=True)
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

def main():
	bot = PlusOne("PlusOne", "plusone.cookie")
	join_rooms(bot)
	asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
	main()
