import asyncio
import websockets

from rocketchat_async.dispatcher import Dispatcher
from rocketchat_async.methods import Connect, Login, Resume, GetChannels, GetChannelsRaw,\
        SendMessage, SendReaction, SendTypingEvent, SubscribeToChannelMessages,\
        SubscribeToChannelMessagesParsed, SubscribeToChannelMessagesRaw, SubscribeToChannelChanges,\
        SubscribeToChannelChangesRaw, Unsubscribe, UpdateMessage



class RocketChat:
    """Represents a connection to RocketChat, exposing the API."""

    class ConnectionClosed(Exception):
        pass

    class ConnectCallFailed(Exception):
        pass

    def __init__(self, verbose=False):
        self.user_id = None
        self.username = None
        self._dispatcher = Dispatcher(verbose=verbose)

    async def start(self, address, username, password):
        ws_connected = asyncio.get_event_loop().create_future()
        ws_connection = self._start(address, ws_connected)
        self._ws_connection_task = asyncio.create_task(ws_connection)
        try:
            await ws_connected
        except (OSError, websockets.InvalidMessage) as e:
            # Exceptions that can arise during temporary network glitches or
            # outages on the remote side.
            # See also https://github.com/aaugustin/websockets/issues/593
            raise self.ConnectCallFailed(e)

        # Connect and login.
        await self._connect()
        self.user_id = await self._login(username, password)
        self.username = username

    async def resume(self, address, username, token):
        ws_connected = asyncio.get_event_loop().create_future()
        ws_connection = self._start(address, ws_connected)
        self._ws_connection_task = asyncio.create_task(ws_connection)
        try:
            await ws_connected
        except (OSError, websockets.InvalidMessage) as e:
            # Exceptions that can arise during temporary network glitches or
            # outages on the remote side.
            # See also https://github.com/aaugustin/websockets/issues/593
            raise self.ConnectCallFailed(e)

        # Connect and login.
        await self._connect()
        self.user_id = await self._resume(token)
        self.username = username

    async def run_forever(self):
        try:
            await self.dispatch_task
        except websockets.ConnectionClosed as e:
            raise self.ConnectionClosed(e)

    async def _start(self, address, connected_fut):
        try:
            async with websockets.connect(address) as websocket:
                self.dispatch_task = self._dispatcher.run(websocket)
                # Notify the caller that login has succeeded.
                connected_fut.set_result(True)
                # Finally, create the ever-running dispatcher loop.
                await self.dispatch_task
        except Exception as e:
            if not connected_fut.done():
                connected_fut.set_exception(e)

    async def _connect(self):
        await Connect.call(self._dispatcher)

    async def _login(self, username, password):
        return await Login.call(self._dispatcher, username, password)

    async def _resume(self, token):
        return await Resume.call(self._dispatcher, token)

    # --> Public API methods start here. <--

    async def get_channels(self):
        """
        Get a list of channels user is currently member of.

        Returns a list of (channel id, channel type) pairs.

        """
        return await GetChannels.call(self._dispatcher)

    async def get_channels_raw(self):
        """
        Get a list of channels user is currently member of.

        Returns a list of channel objects.

        """
        return await GetChannelsRaw.call(self._dispatcher)

    async def send_message(self, text, channel_id, thread_id=None):
        """Send a text message to a channel."""
        sent_msg_id = await SendMessage.call(self._dispatcher, text, channel_id, thread_id)
        return sent_msg_id

    async def update_message(self, text, orig_msg_id ,channel_id, thread_id=None):
        """Update a sent text message"""
        await UpdateMessage.call(self._dispatcher, text, orig_msg_id, channel_id, thread_id)

    async def send_reaction(self, orig_msg_id, emoji):
        """Send a reaction to a specific message."""
        await SendReaction.call(self._dispatcher, orig_msg_id, emoji)

    async def send_typing_event(self, is_typing, channel_id, thread_id=None):
        """Send the `typing` event to a channel."""
        await SendTypingEvent.call(self._dispatcher, is_typing, channel_id, self.username, thread_id)

    async def subscribe_to_channel_messages(self, channel_id, callback):
        """
        Subscribe to all messages in the given channel.

        Returns the subscription ID.

        """
        sub_id = await SubscribeToChannelMessages.call(self._dispatcher,
                                                       channel_id, callback)
        return sub_id
    
    async def subscribe_to_channel_messages_parsed(self, channel_id, callback):
        """
        Subscribe to all messages in the given channel.

        The callback is passed the full message object as dataclass as provided by the API.
        
        Returns the subscription ID.

        """
        sub_id = await SubscribeToChannelMessagesParsed.call(self._dispatcher,
                                                       channel_id, callback)
        return sub_id
    
    

    async def subscribe_to_channel_messages_raw(self, channel_id, callback):
        """
        Subscribe to all messages in the given channel.

        The callback is passed the full message object as provided by the API.

        Returns the subscription ID.

        """
        sub_id = await SubscribeToChannelMessagesRaw.call(self._dispatcher,
                                                          channel_id, callback)
        return sub_id

    async def subscribe_to_channel_changes(self, callback):
        """
        Subscribe to all changes in channels.

        Returns the subscription ID.

        """
        sub_id = await SubscribeToChannelChanges.call(self._dispatcher,
                                                      self.user_id, callback)
        return sub_id

    async def subscribe_to_channel_changes_raw(self, callback):
        """
        Subscribe to all changes in channels.

        The callback is passed the full message object as provided by the API.

        Returns the subscription ID.

        """
        sub_id = await SubscribeToChannelChangesRaw.call(self._dispatcher,
                                                         self.user_id, callback)
        return sub_id

    async def unsubscribe(self, subscription_id):
        """Cancel a subscription."""
        await Unsubscribe.call(self._dispatcher, subscription_id)
