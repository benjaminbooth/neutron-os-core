"""DocFlow built-in providers — auto-import triggers factory registration.

Importing this package registers all built-in providers with DocFlowFactory.
"""

from .generation import *  # noqa: F401,F403
from .storage import *  # noqa: F401,F403
from .feedback import *  # noqa: F401,F403
from .notification import *  # noqa: F401,F403
from .embedding import *  # noqa: F401,F403
