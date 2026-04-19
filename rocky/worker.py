from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    ClassVar,
    Generic,
    Optional,
    ParamSpec,
    TypeVar,
)

FunctionParameters = ParamSpec("FunctionParameters")
ReturnType = TypeVar("ReturnType")
StreamItem = TypeVar("StreamItem")

ROCKY_WORKER_MAX_THREADS = 4


class RockyWorkerEmitter(Generic[StreamItem]):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue,
    ) -> None:
        self._loop = loop
        self._queue = queue

    def __call__(self, item: StreamItem) -> None:
        self._loop.call_soon_threadsafe(self._queue.put_nowait, item)


RockyWorkerProducer = Callable[[RockyWorkerEmitter[StreamItem]], Awaitable[None]]


class RockyWorker:
    _executor: ClassVar[Optional[ThreadPoolExecutor]] = None

    @classmethod
    def executor(cls) -> ThreadPoolExecutor:
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(
                max_workers=ROCKY_WORKER_MAX_THREADS,
                thread_name_prefix="rocky-worker",
            )
        return cls._executor

    @classmethod
    async def run(
        cls,
        function: Callable[FunctionParameters, ReturnType],
        *args: FunctionParameters.args,
        **kwargs: FunctionParameters.kwargs,
    ) -> ReturnType:
        def invoke() -> ReturnType:
            return function(*args, **kwargs)

        return await asyncio.get_running_loop().run_in_executor(cls.executor(), invoke)

    @classmethod
    async def run_async(
        cls,
        factory: Callable[[], Awaitable[ReturnType]],
    ) -> ReturnType:
        def invoke() -> ReturnType:
            return asyncio.run(factory())

        return await asyncio.get_running_loop().run_in_executor(cls.executor(), invoke)

    @classmethod
    async def stream(
        cls,
        producer: RockyWorkerProducer[StreamItem],
    ) -> AsyncIterator[StreamItem]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        completed = object()
        emitter: RockyWorkerEmitter[StreamItem] = RockyWorkerEmitter(loop, queue)

        async def drive() -> None:
            try:
                await producer(emitter)
            except BaseException as failure:
                loop.call_soon_threadsafe(queue.put_nowait, failure)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, completed)

        def invoke() -> None:
            asyncio.run(drive())

        future = loop.run_in_executor(cls.executor(), invoke)
        try:
            while True:
                item = await queue.get()
                if item is completed:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            if not future.done():
                future.cancel()

    @classmethod
    def shutdown(cls) -> None:
        if cls._executor is not None:
            cls._executor.shutdown(wait=False, cancel_futures=True)
            cls._executor = None
