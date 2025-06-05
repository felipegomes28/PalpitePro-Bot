import unittest
from main import bot
from discord.ext import commands

class TestBot(unittest.TestCase):
    def setUp(self):
        self.bot = bot
        self.test_channel = 123456789  # ID do canal de teste

    def test_ping_command(self):
        @self.bot.command()
        async def mock_ctx():
            return type('MockContext', (), {'send': lambda self, msg: msg})
        
        result = await self.bot.get_command('ping').callback(mock_ctx())
        self.assertEqual(result, 'Pong!')

    def test_command_list(self):
        commands = [c.name for c in self.bot.commands]
        self.assertIn('ping', commands)

if __name__ == '__main__':
    unittest.main()