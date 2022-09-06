from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlite.middleware import MiddlewareProtocol

from starlite_bedrock.starlite.db import AsyncScopedSession

__all__ = ["DatabaseSessionMiddleware"]


class DatabaseSessionMiddleware(MiddlewareProtocol):
    """Database Session Middleware

    Args:
        MiddlewareProtocol (_type_): _description_
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    async def _manage_session(message: Message) -> None:
        if 200 <= message["status"] < 300:
            await AsyncScopedSession.commit()
        else:
            await AsyncScopedSession.rollback()
        await AsyncScopedSession.remove()

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] == "http":

            async def send_wrapper(message: Message) -> None:
                if message["type"] == "http.response.start":
                    await self._manage_session(message)
                await send(message)

            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)
