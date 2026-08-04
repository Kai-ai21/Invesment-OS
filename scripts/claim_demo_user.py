#!/usr/bin/env python
"""Claim the seeded demo@local account: give it a real email and a password.

WHY THIS EXISTS. Everything created before authentication landed belongs to a seeded
user with the email "demo@local" and no password. That account cannot be claimed
through /auth/signup for two independent reasons:

  - signup CREATES a user, it never adopts an existing one, so it would leave the
    data behind on demo@local and hand you a new empty account;
  - "demo@local" is not a valid email address anyway — no dot after the @ — so
    EmailStr rejects it and there is nothing to log in as.

So this is a one-off migration, not a feature: it renames the row that already owns
the data and gives it a password. Run it once and it is done — a second run reports
that demo@local is gone and changes nothing.

⚠️ IT UPDATES, IT DOES NOT MOVE ANYTHING. No thesis, holding, alert or reflection is
touched — they all reference the user by id, and the id does not change. That is the
whole point of renaming the row rather than creating a new user and reassigning: there
is no window in which a row could be left pointing at an account that no longer exists.
The counts printed at the end are there so you can see that for yourself.

USAGE
    python -m scripts.claim_demo_user you@example.com 'your-password'
    python -m scripts.claim_demo_user you@example.com          # prompts, hides input

⚠️ ON PASSING THE PASSWORD AS AN ARGUMENT. It is accepted because it was asked for and
it is convenient, but a command-line argument is not private: it lands in your shell
history file, and while the process runs it is visible in `ps` to any other user on
the machine. Omitting it prompts instead, which avoids both. If you do pass it inline,
consider a leading space (bash/zsh with HIST_IGNORE_SPACE) or clearing the history
entry afterwards.
"""

from __future__ import annotations

import argparse
import getpass
import sys

DEMO_EMAIL = "demo@local"


def _fail(message: str) -> int:
    """One exit path for every refusal, so nothing ever half-runs.

    Everything this script can refuse for is checked BEFORE the single commit at the
    end, and each refusal prints what to do about it rather than a traceback.
    """
    print(f"Refusing to run: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="claim_demo_user",
        description=f"Give the seeded {DEMO_EMAIL} account a real email and password.",
    )
    parser.add_argument("email", help="the email address you want to log in with")
    parser.add_argument(
        "password",
        nargs="?",
        default=None,
        help="the password to set. Omit it to be prompted instead, which keeps it "
        "out of your shell history and out of `ps`.",
    )
    args = parser.parse_args(argv)

    # ⚠️ IMPORTED INSIDE main(), NOT AT MODULE LEVEL, on purpose. backend.core.security
    # reads JWT_SECRET at import and raises when it is missing — correct for a server,
    # but at module scope here it would fire during argparse setup and answer
    # `--help` with a stack trace. Deferring it means the failure arrives as a
    # sentence, after the arguments have been understood.
    try:
        from pydantic import ValidationError

        from backend.api.schemas import SignupRequest
        from backend.core.security import hash_password
        from backend.models.alert import Alert
        from backend.models.claim import Claim  # noqa: F401 — Thesis.claims needs it
        from backend.models.database import SessionLocal, init_db
        from backend.models.holding import Holding
        from backend.models.pattern import Pattern
        from backend.models.post_mortem import PostMortem
        from backend.models.thesis import Thesis
        from backend.models.user import User
    except RuntimeError as exc:
        # Overwhelmingly: JWT_SECRET unset. The message from core/security already
        # says how to generate one, so it is passed through rather than paraphrased.
        return _fail(str(exc))

    password = args.password
    if password is None:
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Confirm password: "):
            return _fail("the two passwords did not match. Nothing was changed.")

    # ⚠️ VALIDATED BY THE SIGNUP SCHEMA ITSELF, not by rules retyped here. SignupRequest
    # is what /auth/signup validates against, so this enforces exactly the same email
    # format, the same 8-character floor and the same 72-BYTE bcrypt ceiling. Retyping
    # them would create a second source of truth that drifts, and the drift would show
    # up as an account this script happily created and the API cannot authenticate.
    #
    # It also does the trim-and-lowercase normalisation, which matters more than it
    # looks: login normalises the address before looking it up, so an email stored
    # with different casing is an account you can never log into.
    try:
        validated = SignupRequest(email=args.email, password=password)
    except ValidationError as exc:
        problems = "; ".join(error["msg"] for error in exc.errors())
        return _fail(f"{problems} Nothing was changed.")

    email = validated.email

    # The same migrations the app runs at startup. Harmless when they have already
    # been applied, and it means this script works against a database that has not
    # been opened by the backend since the auth columns were added.
    init_db()

    with SessionLocal() as db:
        demo = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if demo is None:
            # Distinguished from the generic case because the likeliest cause is that
            # this has already been run, and "not found" alone would read as a bug.
            already = db.query(User).count()
            return _fail(
                f'no user with the email "{DEMO_EMAIL}" exists in this database.\n'
                f"  The database holds {already} user(s).\n"
                "  If you have already run this script, it is done — log in with the "
                "email you set.\n"
                "  Otherwise check you are pointing at the right database "
                "(backend/investment_os.db)."
            )

        # ⚠️ CHECKED BEFORE ANYTHING IS WRITTEN. `users.email` is uniquely indexed, so
        # a collision would otherwise surface as an IntegrityError from the commit —
        # after the password hash had been computed and assigned, and with a traceback
        # instead of an explanation.
        clash = (
            db.query(User)
            .filter(User.email == email, User.id != demo.id)
            .first()
        )
        if clash is not None:
            return _fail(
                f'the email "{email}" already belongs to a different account '
                f"(id {clash.id}).\n"
                "  Pick another address, or delete that account first. Nothing was "
                "changed."
            )

        # Counted BEFORE the change, so the numbers are what was attached to the row
        # on the way in. Re-counted after the commit below and compared — that is what
        # turns this from a reassuring printout into an actual check.
        #
        # ⚠️ ALERTS AND REFLECTIONS ARE COUNTED THROUGH THE THESIS, because that is how
        # they are owned — neither table has a user_id of its own. Counting them with a
        # direct filter would silently return zero and report that nothing was attached.
        def counts() -> dict[str, int]:
            thesis_ids = [
                row[0] for row in db.query(Thesis.id).filter(Thesis.user_id == demo.id)
            ]
            return {
                "theses": len(thesis_ids),
                "claims": (
                    db.query(Claim).filter(Claim.thesis_id.in_(thesis_ids)).count()
                    if thesis_ids
                    else 0
                ),
                "holdings": db.query(Holding)
                .filter(Holding.user_id == demo.id)
                .count(),
                "alerts": (
                    db.query(Alert).filter(Alert.thesis_id.in_(thesis_ids)).count()
                    if thesis_ids
                    else 0
                ),
                "post-mortems": (
                    db.query(PostMortem)
                    .filter(PostMortem.thesis_id.in_(thesis_ids))
                    .count()
                    if thesis_ids
                    else 0
                ),
                "patterns": db.query(Pattern)
                .filter(Pattern.user_id == demo.id)
                .count(),
            }

        before = counts()
        user_id = demo.id

        # The actual change: two columns on one row. The primary key is untouched, so
        # every foreign key pointing at it still points at it.
        demo.email = email
        demo.password_hash = hash_password(validated.password)
        db.commit()

        after = counts()

    print(f"Claimed {DEMO_EMAIL} -> {email}")
    print(f"  user id: {user_id} (unchanged, so nothing was reassigned)")
    print("  attached to this account:")
    for label, count in after.items():
        print(f"    {count:>4}  {label}")

    if before != after:
        # Cannot happen — nothing here deletes — but if it ever did, silence would be
        # the worst possible response.
        print(
            "\n⚠️  WARNING: the counts changed during the update. Before: "
            f"{before}. After: {after}. Investigate before relying on this.",
            file=sys.stderr,
        )
        return 1

    print("\nNothing was orphaned. Log in at /login with the email and password above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
