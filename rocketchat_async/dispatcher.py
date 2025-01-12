import asyncio
import json
from typing import Any


class Dispatcher:
    """Match websockets calls with responses and manage callbacks."""

    def __init__(self, verbose=False):
        self._websocket: Any = None
        self._futures = {}  # ID -> asyncio Future (resolved with the response)
        self._verbose = verbose

        # ID -> registered callback (called when the msg arrives)
        self._callbacks = {}

    def run(self, websocket):
        self._websocket = websocket
        # Start listening to incoming messages, executing callbacks,
        # if appropriate.
        return asyncio.create_task(self._process_incoming())

    async def call_method(self, msg, msg_id=None):
        if self._verbose:
            print(f'Outgoing: {msg}')
        if (msg_id is None):
            await self._websocket.send(json.dumps(msg))
        else:
            fut = asyncio.get_event_loop().create_future()
            self._futures[msg_id] = fut
            await self._websocket.send(json.dumps(msg))
            return await fut

    async def create_subscription(self, msg, callback):
        if self._verbose:
            print(f'Outgoing: {msg}')
        self._callbacks[msg['params'][0]] = callback # Room ID
        await self._websocket.send(json.dumps(msg))

    async def _process_incoming(self):
        try:
            while True:
                await self._process_incoming_event()
        except Exception as err:
            for fut in self._futures.values():
                # Propagate the exception to all awaiters to not get stuck.
                fut.set_exception(err)
            raise err

    async def _process_incoming_event(self):
        msg = await self._websocket.recv()
        if self._verbose:
            print(f'Incoming: {msg}')
        parsed = json.loads(msg)
        if parsed['msg'] == 'result':
            msg_id = parsed['id']
            if msg_id in self._futures:
                self._futures[msg_id].set_result(parsed)
                del self._futures[msg_id]
        elif parsed['msg'] == 'changed':  # Subscription update.
            stream_name = parsed['fields']['eventName'] # Room ID
            if stream_name in self._callbacks:
                self._callbacks[stream_name](parsed)
        elif parsed['msg'] in ['ready', 'connected', 'added', 'updated',
                               'nosub']:
            return  # Nothing to do.
        elif parsed['msg'] == 'ping':
            asyncio.create_task(self.call_method({'msg': 'pong'}))
        elif parsed['msg'] == 'error':
            if self._verbose:
                print(f'Remote error: {msg}')
        else:
            if self._verbose:
                print(f'Unknown message: {msg}')
