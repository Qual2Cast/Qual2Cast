"""common/cli_models.py: which CLI errors stop a run."""

import cli_models as cm


def test_subscription_limit_stops_the_run():
    assert cm.is_fatal("HTTP 429: You've hit your limit · resets 8pm (America/New_York)")
    assert cm.is_fatal("Not logged in · Please run /login")


def test_a_bad_answer_does_not_stop_the_run():
    assert not cm.is_fatal("Expecting value: line 1 column 1 (char 0)")
