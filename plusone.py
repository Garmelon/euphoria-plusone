import yaboli
from yaboli.utils import *
import asyncio
import re
import sys



class PointDB(yaboli.Database):
	@yaboli.Database.operation
	def initialize(conn):
		cur = conn.cursor()
		cur.execute((
			"CREATE TABLE IF NOT EXISTS Points ("
				"nick TEXT UNIQUE NOT NULL,"
				"points INTEGER"
			")"
		))
		conn.commit()
	
	@yaboli.Database.operation
	def add_point(conn, nick):
		nick = mention_reduced(nick)
		cur = conn.cursor()
		
		cur.execute("INSERT OR IGNORE INTO Points (nick, points) VALUES (?, 0)", (nick,))
		cur.execute("UPDATE Points SET points=points+1 WHERE nick=?", (nick,))
		conn.commit()
	
	@yaboli.Database.operation
	def points_of(conn, nick):
		nick = mention_reduced(nick)
		cur = conn.cursor()
		
		cur.execute("SELECT points FROM Points WHERE nick=?", (nick,))
		res = cur.fetchone()
		if res is not None:
			return res[0]
		else:
			return 0

class PlusOne(yaboli.Bot):
	"""
	Count +1s awarded to users by other users.
	"""
	
	PLUSONE_RE = r"(\+1|:\+1:|:bronze(!\?|\?!)?:)\s*(.*)"
	MENTION_RE = r"((for|to)\s+)?@(\S+)"
	
	def __init__(self, db):
		super().__init__("PlusOne")
		
		self.db = db
		
		self.help_general = "/me counts :+1:s."
		self.help_specific = (
			"Counts +1/:+1:/:bronze:s: Simply reply \"+1\" to someone's message to award them a point.\n"
			"Alternatively, specify a person with: \"+1 [to|for] @person\"\n"
			"!points - show your own points\n"
			"!points <person1> [<person2> ...] - list other people's points\n\n"
			"Created by @Garmy using yaboli.\n"
			"For additional info, try \"!help @{nick} <topic>\". Topics:\n"
		)
		self.help_specific += self.list_help_topics()
		self.ping_message = ":bronze!?:"
		
		self.register_command("points", self.command_points, specific=False)
		self.register_trigger(self.PLUSONE_RE, self.trigger_plusone)
	
	async def trigger_plusone(self, message, match):
		nick = None
		specific = re.match(self.MENTION_RE, match.group(3))

		if specific:
			nick = specific.group(3)
		elif message.parent:
			parent_message = await self.room.get_message(message.parent)
			nick = parent_message.sender.nick
		
		if nick is None:
			await self.room.send("You can't +1 nothing...", message.mid)
		elif similar(nick, message.sender.nick):
			await self.room.send("Don't +1 yourself, that's... It just doesn't work that way, alright?", message.mid)
		else:
			await self.db.add_point(nick)
			await self.room.send(f"Point for user {mention(nick)} registered.", message.mid)
	
	async def command_points(self, message, argstr):
		args = self.parse_args(argstr)
		if not args:
			points = await self.db.points_of(message.sender.nick)
			await self.room.send(
				f"You have {points} point{'s' if points != 1 else ''}.",
				message.mid
			)
		else:
			response = []
			for arg in args:
				if arg[:1] == "@":
					nick = arg[1:]
					points = await self.db.points_of(nick)
					response.append(f"@{mention(nick)} has {points} point{'' if points == 1 else 's'}.")
				else:
					response.append(f"{arg!r} is not a mention.")
			await self.room.send("\n".join(response), message.mid)

def main():
	if len(sys.argv) == 3:
		db = PointDB(sys.argv[2])
		asyncio.get_event_loop().run_until_complete(db.initialize())
		run_bot(PlusOne, sys.argv[1], db)
	else:
		print("USAGE:")
		print(f"  {sys.argv[0]} <room> <pointsdb>")
		return

if __name__ == "__main__":
	main()
