import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

class AsyncExecutor:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def run_blocking(self, func, *args):
        """Execute blocking functions asynchronously"""
        return await self.loop.run_in_executor(
            self.executor, 
            partial(func, *args)
        )

    async def safe_execute(self, func, *args):
        """Wrapper with error handling"""
        try:
            return await self.run_blocking(func, *args)
        except Exception as e:
            print(f"Async execution failed: {str(e)}")
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
        self.loop.close()

    @staticmethod
    async def gather(*coroutines):
        """Wrapper for asyncio.gather"""
        return await asyncio.gather(*coroutines)
