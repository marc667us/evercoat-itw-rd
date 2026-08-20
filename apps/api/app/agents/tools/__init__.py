"""MSD's tools.

Plain Python with typed signatures. No framework is imported here and
none may be: `CLAUDE.md` §4 confines the orchestration framework to
`app/agents/graphs/`, and the point of that confinement is that these
functions stay callable and testable on their own.

Every tool takes the CALLER'S OWN SESSION. None takes a `user_id` it
could impersonate — the same rule `retrieve_for_question` states and for
the same reason.
"""

from app.agents.tools.guidance import explain_the_application
from app.agents.tools.records import find_records
from app.agents.tools.work import pending_work

__all__ = ["explain_the_application", "find_records", "pending_work"]
