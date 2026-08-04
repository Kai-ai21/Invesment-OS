# Present so pytest puts the repo root on sys.path, making `backend.*` importable from tests.

import os

# ⚠️ SET BEFORE ANY backend.* IMPORT, which is why it is at module scope in the root
# conftest rather than in a fixture. backend/core/security.py reads JWT_SECRET AT
# IMPORT and raises when it is missing — deliberately, so a misconfigured deployment
# dies at startup instead of signing tokens with a default. A fixture would run far
# too late: the import happens during collection.
#
# `setdefault`, not assignment: a real JWT_SECRET in the environment still wins, so
# this cannot mask what a developer is actually running with.
#
# The value is obviously fake and obviously test-only. It is long enough to clear the
# 32-character floor, which is the point — the length check itself is exercised in
# tests/test_auth.py, in a subprocess with a deliberately short one.
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-not-for-any-real-deployment")
