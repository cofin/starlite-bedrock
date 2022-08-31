from typing import TYPE_CHECKING

from starlite_bedrock.starlite.db import AsyncScopedSession

if TYPE_CHECKING:
    from starlite.response import Response


async def session_after_request(response: "Response") -> "Response":
    """
    Passed to `Starlite.after_request`.

    Inspects `response` to determine if we should commit, or rollback the database
    transaction.

    Finally, calls `remove()` on the scoped session.

    Parameters
    ----------
    response : Response
        The outgoing response.

    Returns
    -------
    Response
        Passed through from input assuming that commit/roll back does not error.
    """
    if 200 <= response.status_code < 300:
        await AsyncScopedSession.commit()
    else:
        await AsyncScopedSession.rollback()
    await AsyncScopedSession.remove()
    return response
