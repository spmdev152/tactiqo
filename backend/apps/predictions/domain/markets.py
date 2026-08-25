from apps.predictions.domain.enums import PredictionMarket, PredictionSelection

# Both structures below are the order the public contract promises, so the
# interface renders what it is handed instead of holding a second copy of this
# vocabulary and having to be kept in step with it. Neither is derivable: the
# enumerations declare their members for readability, and a market's selections
# are neither alphabetical nor a partition of the enumeration.
MARKET_ORDER: tuple[PredictionMarket, ...] = (
    PredictionMarket.FULLTIME_RESULT,
    PredictionMarket.DOUBLE_CHANCE,
    PredictionMarket.BOTH_TEAMS_TO_SCORE,
    PredictionMarket.OVER_UNDER_1_5,
    PredictionMarket.OVER_UNDER_2_5,
    PredictionMarket.OVER_UNDER_3_5,
    PredictionMarket.OVER_UNDER_4_5,
    PredictionMarket.TEAM_TO_SCORE_FIRST,
    PredictionMarket.FIRST_HALF_RESULT,
    PredictionMarket.HALF_TIME_FULL_TIME,
    PredictionMarket.CORRECT_SCORE,
)

_RESULT_SELECTIONS = (
    PredictionSelection.HOME,
    PredictionSelection.DRAW,
    PredictionSelection.AWAY,
)

_TWO_WAY_SELECTIONS = (PredictionSelection.YES, PredictionSelection.NO)

MARKET_SELECTIONS: dict[PredictionMarket, tuple[PredictionSelection, ...]] = {
    PredictionMarket.FULLTIME_RESULT: _RESULT_SELECTIONS,
    PredictionMarket.DOUBLE_CHANCE: (
        PredictionSelection.HOME_OR_DRAW,
        PredictionSelection.HOME_OR_AWAY,
        PredictionSelection.DRAW_OR_AWAY,
    ),
    PredictionMarket.BOTH_TEAMS_TO_SCORE: _TWO_WAY_SELECTIONS,
    PredictionMarket.OVER_UNDER_1_5: _TWO_WAY_SELECTIONS,
    PredictionMarket.OVER_UNDER_2_5: _TWO_WAY_SELECTIONS,
    PredictionMarket.OVER_UNDER_3_5: _TWO_WAY_SELECTIONS,
    PredictionMarket.OVER_UNDER_4_5: _TWO_WAY_SELECTIONS,
    PredictionMarket.TEAM_TO_SCORE_FIRST: (
        PredictionSelection.HOME,
        PredictionSelection.AWAY,
        PredictionSelection.NO_GOAL,
    ),
    PredictionMarket.FIRST_HALF_RESULT: _RESULT_SELECTIONS,
    PredictionMarket.HALF_TIME_FULL_TIME: (
        PredictionSelection.HOME_THEN_HOME,
        PredictionSelection.HOME_THEN_DRAW,
        PredictionSelection.HOME_THEN_AWAY,
        PredictionSelection.DRAW_THEN_HOME,
        PredictionSelection.DRAW_THEN_DRAW,
        PredictionSelection.DRAW_THEN_AWAY,
        PredictionSelection.AWAY_THEN_HOME,
        PredictionSelection.AWAY_THEN_DRAW,
        PredictionSelection.AWAY_THEN_AWAY,
    ),
    PredictionMarket.CORRECT_SCORE: (
        PredictionSelection.SCORE_0_0,
        PredictionSelection.SCORE_0_1,
        PredictionSelection.SCORE_0_2,
        PredictionSelection.SCORE_0_3,
        PredictionSelection.SCORE_1_0,
        PredictionSelection.SCORE_1_1,
        PredictionSelection.SCORE_1_2,
        PredictionSelection.SCORE_1_3,
        PredictionSelection.SCORE_2_0,
        PredictionSelection.SCORE_2_1,
        PredictionSelection.SCORE_2_2,
        PredictionSelection.SCORE_2_3,
        PredictionSelection.SCORE_3_0,
        PredictionSelection.SCORE_3_1,
        PredictionSelection.SCORE_3_2,
        PredictionSelection.SCORE_3_3,
        PredictionSelection.ANY_OTHER_HOME_WIN,
        PredictionSelection.ANY_OTHER_DRAW,
        PredictionSelection.ANY_OTHER_AWAY_WIN,
    ),
}
