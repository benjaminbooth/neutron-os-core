# Root conftest — makes shared fixtures available to ALL test directories,
# including colocated extension tests in src/neutron_os/extensions/builtins/.
#
# Fixtures are defined in tests/conftest.py and re-exported here so that
# pytest discovers them regardless of which testpath a test lives under.

from tests.conftest import *  # noqa: F401,F403
