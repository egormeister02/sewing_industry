# database.py
'''
import aiosqlite
from contextlib import asynccontextmanager
from credentials import DB_PATH 

async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        with open('schema.sql', 'r') as f:
            schema = f.read()
        await conn.executescript(schema)
        await conn.commit()

class Database:
    def __init__(self):
        self.conn = None
    
    @asynccontextmanager
    async def get_connection(self):
        if not self.conn:
            self.conn = await aiosqlite.connect(DB_PATH)
        yield self.conn
    
    @asynccontextmanager
    async def execute(self, query, args=()):
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, args)
            try:
                yield cursor
            finally:
                await conn.commit()
    
    async def fetchall(self, cursor):
        return await cursor.fetchall()
'''