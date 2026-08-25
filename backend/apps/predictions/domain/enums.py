from django.db import models


class PredictionMarket(models.TextChoices):
    """
    Prediction market the platform publishes probabilities for.

    The provider models twenty-eight markets. This vocabulary keeps the eleven
    the product renders and drops the per-team goal lines and the corner lines,
    which together account for forty-three of the fifty-three selections a
    fixture would otherwise carry. The provider identifies a market by a numeric
    type id; that id is mapped onto a member of this enumeration inside the
    Sportmonks boundary and never reaches the column, the API, or the interface.

    Attributes
    ----------
    FULLTIME_RESULT : str
        Winner after ninety minutes, serialized as ``"fulltime_result"``.
    DOUBLE_CHANCE : str
        Two of the three full-time outcomes together, serialized as
        ``"double_chance"``. Its selections overlap, so they sum to roughly two
        hundred rather than to a hundred.
    FIRST_HALF_RESULT : str
        Winner at half time, serialized as ``"first_half_result"``.
    HALF_TIME_FULL_TIME : str
        Half-time and full-time outcome as one pair, serialized as
        ``"half_time_full_time"``.
    CORRECT_SCORE : str
        Exact score, serialized as ``"correct_score"``. Its nineteen selections
        cover every score up to three goals a side and bucket the rest by
        outcome.
    TEAM_TO_SCORE_FIRST : str
        Side that opens the scoring, serialized as
        ``"team_to_score_first"``. Its third selection is a goalless match
        rather than a draw.
    BOTH_TEAMS_TO_SCORE : str
        Whether both sides score, serialized as ``"both_teams_to_score"``.
    OVER_UNDER_1_5 : str
        Whether the match produces two goals or more, serialized as
        ``"over_under_1_5"``.
    OVER_UNDER_2_5 : str
        Whether the match produces three goals or more, serialized as
        ``"over_under_2_5"``.
    OVER_UNDER_3_5 : str
        Whether the match produces four goals or more, serialized as
        ``"over_under_3_5"``.
    OVER_UNDER_4_5 : str
        Whether the match produces five goals or more, serialized as
        ``"over_under_4_5"``.
    """

    FULLTIME_RESULT = "fulltime_result", "Full-time result"
    DOUBLE_CHANCE = "double_chance", "Double chance"
    FIRST_HALF_RESULT = "first_half_result", "First-half result"
    HALF_TIME_FULL_TIME = "half_time_full_time", "Half-time / full-time"
    CORRECT_SCORE = "correct_score", "Correct score"
    TEAM_TO_SCORE_FIRST = "team_to_score_first", "Team to score first"
    BOTH_TEAMS_TO_SCORE = "both_teams_to_score", "Both teams to score"
    OVER_UNDER_1_5 = "over_under_1_5", "Over/under 1.5"
    OVER_UNDER_2_5 = "over_under_2_5", "Over/under 2.5"
    OVER_UNDER_3_5 = "over_under_3_5", "Over/under 3.5"
    OVER_UNDER_4_5 = "over_under_4_5", "Over/under 4.5"


class PredictionSelection(models.TextChoices):
    """
    Outcome within a prediction market, in the platform's own vocabulary.

    One enumeration covers every market rather than one per market, because the
    column that stores it is one column and a reader of the table needs a single
    closed set to check it against. Which selections belong to which market is
    stated separately, by ``MARKET_SELECTIONS``.

    The provider keys are deliberately not reused. Three of them are actively
    misleading: ``draw`` is how the team-to-score-first market spells a goalless
    match, and ``home_away`` means "home or away" in the double-chance market
    but "home at half time, away at full time" in the half-time/full-time
    market, so one provider key maps to two different selections here. The
    correct-score keys are score-shaped strings such as ``"0-1"``, which no
    identifier can carry.

    Attributes
    ----------
    HOME : str
        Home side wins, serialized as ``"home"``.
    DRAW : str
        Match is drawn, serialized as ``"draw"``.
    AWAY : str
        Away side wins, serialized as ``"away"``.
    HOME_OR_DRAW : str
        Home side wins or the match is drawn, serialized as
        ``"home_or_draw"``.
    DRAW_OR_AWAY : str
        Match is drawn or the away side wins, serialized as
        ``"draw_or_away"``.
    HOME_OR_AWAY : str
        Either side wins, serialized as ``"home_or_away"``.
    NO_GOAL : str
        Nobody scores, serialized as ``"no_goal"``. It is the third selection of
        the team-to-score-first market, where a goalless match is the only way
        for neither side to open the scoring.
    YES : str
        Condition of a two-way market holds, serialized as ``"yes"``.
    NO : str
        Condition of a two-way market does not hold, serialized as ``"no"``.
    HOME_THEN_HOME : str
        Home side leads at half time and wins, serialized as
        ``"home_then_home"``.
    HOME_THEN_DRAW : str
        Home side leads at half time and the match is drawn, serialized as
        ``"home_then_draw"``.
    HOME_THEN_AWAY : str
        Home side leads at half time and the away side wins, serialized as
        ``"home_then_away"``.
    DRAW_THEN_HOME : str
        Level at half time, home side wins, serialized as
        ``"draw_then_home"``.
    DRAW_THEN_DRAW : str
        Level at half time and at full time, serialized as
        ``"draw_then_draw"``.
    DRAW_THEN_AWAY : str
        Level at half time, away side wins, serialized as
        ``"draw_then_away"``.
    AWAY_THEN_HOME : str
        Away side leads at half time and the home side wins, serialized as
        ``"away_then_home"``.
    AWAY_THEN_DRAW : str
        Away side leads at half time and the match is drawn, serialized as
        ``"away_then_draw"``.
    AWAY_THEN_AWAY : str
        Away side leads at half time and wins, serialized as
        ``"away_then_away"``.
    SCORE_0_0 : str
        Match ends nil-nil, serialized as ``"score_0_0"``.
    SCORE_0_1 : str
        Match ends nil-one, serialized as ``"score_0_1"``.
    SCORE_0_2 : str
        Match ends nil-two, serialized as ``"score_0_2"``.
    SCORE_0_3 : str
        Match ends nil-three, serialized as ``"score_0_3"``.
    SCORE_1_0 : str
        Match ends one-nil, serialized as ``"score_1_0"``.
    SCORE_1_1 : str
        Match ends one-one, serialized as ``"score_1_1"``.
    SCORE_1_2 : str
        Match ends one-two, serialized as ``"score_1_2"``.
    SCORE_1_3 : str
        Match ends one-three, serialized as ``"score_1_3"``.
    SCORE_2_0 : str
        Match ends two-nil, serialized as ``"score_2_0"``.
    SCORE_2_1 : str
        Match ends two-one, serialized as ``"score_2_1"``.
    SCORE_2_2 : str
        Match ends two-two, serialized as ``"score_2_2"``.
    SCORE_2_3 : str
        Match ends two-three, serialized as ``"score_2_3"``.
    SCORE_3_0 : str
        Match ends three-nil, serialized as ``"score_3_0"``.
    SCORE_3_1 : str
        Match ends three-one, serialized as ``"score_3_1"``.
    SCORE_3_2 : str
        Match ends three-two, serialized as ``"score_3_2"``.
    SCORE_3_3 : str
        Match ends three-three, serialized as ``"score_3_3"``.
    ANY_OTHER_HOME_WIN : str
        Home side wins by a score the enumerated ones do not cover, serialized
        as ``"any_other_home_win"``.
    ANY_OTHER_DRAW : str
        Match is drawn by a score the enumerated ones do not cover, serialized
        as ``"any_other_draw"``.
    ANY_OTHER_AWAY_WIN : str
        Away side wins by a score the enumerated ones do not cover, serialized
        as ``"any_other_away_win"``.
    """

    HOME = "home"
    DRAW = "draw"
    AWAY = "away"
    HOME_OR_DRAW = "home_or_draw"
    DRAW_OR_AWAY = "draw_or_away"
    HOME_OR_AWAY = "home_or_away"
    NO_GOAL = "no_goal"
    YES = "yes"
    NO = "no"
    HOME_THEN_HOME = "home_then_home"
    HOME_THEN_DRAW = "home_then_draw"
    HOME_THEN_AWAY = "home_then_away"
    DRAW_THEN_HOME = "draw_then_home"
    DRAW_THEN_DRAW = "draw_then_draw"
    DRAW_THEN_AWAY = "draw_then_away"
    AWAY_THEN_HOME = "away_then_home"
    AWAY_THEN_DRAW = "away_then_draw"
    AWAY_THEN_AWAY = "away_then_away"
    SCORE_0_0 = "score_0_0"
    SCORE_0_1 = "score_0_1"
    SCORE_0_2 = "score_0_2"
    SCORE_0_3 = "score_0_3"
    SCORE_1_0 = "score_1_0"
    SCORE_1_1 = "score_1_1"
    SCORE_1_2 = "score_1_2"
    SCORE_1_3 = "score_1_3"
    SCORE_2_0 = "score_2_0"
    SCORE_2_1 = "score_2_1"
    SCORE_2_2 = "score_2_2"
    SCORE_2_3 = "score_2_3"
    SCORE_3_0 = "score_3_0"
    SCORE_3_1 = "score_3_1"
    SCORE_3_2 = "score_3_2"
    SCORE_3_3 = "score_3_3"
    ANY_OTHER_HOME_WIN = "any_other_home_win"
    ANY_OTHER_DRAW = "any_other_draw"
    ANY_OTHER_AWAY_WIN = "any_other_away_win"


class PredictionReliability(models.TextChoices):
    """
    How well the provider's model has performed on a market in a competition.

    The provider grades a market per competition rather than per fixture, and
    publishes the grade as one of these four words. It is carried through
    unchanged because it is the honest counterweight to a probability: a
    correct-score number graded ``POOR`` and one graded ``HIGH`` look identical
    on a bar, and the reader is the one who should decide what to do about that.

    The members are declared weakest first, so the declaration order is the
    order a reader ranks them in.

    Attributes
    ----------
    POOR : str
        Model performs badly on this market in this competition, serialized as
        ``"poor"``.
    MEDIUM : str
        Model performs acceptably, serialized as ``"medium"``.
    GOOD : str
        Model performs well, serialized as ``"good"``.
    HIGH : str
        Model performs very well, serialized as ``"high"``.
    """

    POOR = "poor"
    MEDIUM = "medium"
    GOOD = "good"
    HIGH = "high"
