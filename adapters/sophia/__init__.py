"""Sophia academic review product adapter.

C10 hardens the longitudinal claim-scope classifier at package import so
``associated with improved outcomes`` is not misread as causal merely because
an outcome adjective contains causal-looking vocabulary. The patch is local to
this C10 branch and remains deterministic and inspectable.
"""

from adapters.sophia.c10_scope import install_longitudinal_scope_patch
from adapters.sophia import longitudinal_speculum as _longitudinal_speculum

install_longitudinal_scope_patch(_longitudinal_speculum)
