from django.db import models


class MatchSide(models.TextChoices):
    """
    Side of a match a team occupied, in the vocabulary the platform publishes.

    The provider states the side twice, as a ``location`` string on every
    statistic row and implicitly through ``participant_id``. Both are read at the
    boundary and reconciled against each other, and only this vocabulary reaches
    the column, the API, or the interface.

    Attributes
    ----------
    HOME : str
        Team played at its own ground, serialized as ``"home"``.
    AWAY : str
        Team played away from its own ground, serialized as ``"away"``.
    """

    HOME = "home", "Home"
    AWAY = "away", "Away"


class FormRange(models.TextChoices):
    """
    Window of completed matches a form sample is drawn from.

    Every window is confined to the season the fixture being read belongs to,
    and the two short ones count matches rather than days inside it, so they
    answer what a reader means by recent form regardless of how a calendar has
    been arranged around international breaks. A pre-match read is about form in
    the campaign being played: a window spanning two of them makes one figure
    mean two different things, and what a club did last season is not evidence
    about this one. While a season has produced three matches or fewer the three
    windows therefore coincide, which is accepted rather than worked around, and
    each sample states how many matches it found, so a short one is visible
    rather than implied.

    Attributes
    ----------
    LAST_3 : str
        Three most recent completed matches of the season, serialized as
        ``"last_3"``.
    LAST_6 : str
        Six most recent completed matches of the season, serialized as
        ``"last_6"``.
    SEASON : str
        Every completed match of the season the fixture belongs to, serialized
        as ``"season"``, which makes it the widest of the three.
    """

    LAST_3 = "last_3", "Last 3"
    LAST_6 = "last_6", "Last 6"
    SEASON = "season", "Season"


class FormScope(models.TextChoices):
    """
    Whether a form sample is narrowed to the side the team will occupy.

    The narrow scope resolves per team rather than globally: for the home team of
    the fixture being read it keeps that team's home matches, and for the away
    team it keeps that team's away matches. Any other reading would compare one
    team's home record against the other team's whole record.

    Attributes
    ----------
    OVERALL : str
        Every completed match in the range, serialized as ``"overall"``.
    VENUE : str
        Only the matches the team played on the side it will occupy in this
        fixture, serialized as ``"venue"``.
    """

    OVERALL = "overall", "Overall"
    VENUE = "venue", "Home / away"


class FormMetric(models.TextChoices):
    """
    Figure a form sample publishes, in the vocabulary the platform owns.

    The provider publishes forty-six statistic types per side, thirty-five of
    them on every side of every match. This vocabulary is the twenty-five figures
    the product renders, five of which also state what the opposition recorded
    against the team. Three of them are not provider figures at all: the result
    shares come from the stored fixture score, because the provider omits its
    goals type at nought and a goalless match would otherwise read as missing
    data. Three more are ratios the boundary never stores, because the mean of
    per-match percentages is not the percentage over those matches; they are
    computed from a summed numerator over a summed denominator.

    A percentage member carries a value between nought and a hundred. Every other
    member carries a per-match average, which is why a count the provider omits
    at nought is read as nought rather than dropped.

    Attributes
    ----------
    WIN_SHARE : str
        Share of the sample the team won, serialized as ``"win_share"``.
    DRAW_SHARE : str
        Share of the sample the team drew, serialized as ``"draw_share"``.
    LOSS_SHARE : str
        Share of the sample the team lost, serialized as ``"loss_share"``.
    GOALS : str
        Goals scored per match, serialized as ``"goals"``. Also states the goals
        conceded per match.
    SHOTS : str
        Shots taken per match, serialized as ``"shots"``. Also states the shots
        faced per match.
    SHOTS_ON_TARGET : str
        Shots on target per match, serialized as ``"shots_on_target"``. Also
        states the shots on target faced per match.
    SHOTS_INSIDE_BOX : str
        Shots taken from inside the box per match, serialized as
        ``"shots_inside_box"``.
    BIG_CHANCES_CREATED : str
        Clear chances created per match, serialized as
        ``"big_chances_created"``. Also states the clear chances conceded per
        match.
    KEY_PASSES : str
        Passes leading directly to a shot per match, serialized as
        ``"key_passes"``.
    CORNERS : str
        Corners won per match, serialized as ``"corners"``. Also states the
        corners conceded per match.
    POSSESSION : str
        Share of the ball, serialized as ``"possession"``. It is the one
        provider percentage stored as published, because it is already normalized
        to a single match and its two sides sum to a hundred, so no opposing
        figure is published for it.
    PASSES : str
        Passes attempted per match, serialized as ``"passes"``.
    PASS_ACCURACY : str
        Share of passes completed, serialized as ``"pass_accuracy"``, as
        completed passes over attempted passes across the whole sample.
    CROSSES : str
        Crosses attempted per match, serialized as ``"crosses"``.
    CROSS_ACCURACY : str
        Share of crosses completed, serialized as ``"cross_accuracy"``, as
        accurate crosses over attempted crosses across the whole sample.
    DRIBBLE_SUCCESS : str
        Share of dribbles completed, serialized as ``"dribble_success"``, as
        successful dribbles over attempted dribbles across the whole sample.
    SAVES : str
        Saves made per match, serialized as ``"saves"``.
    TACKLES : str
        Tackles made per match, serialized as ``"tackles"``.
    INTERCEPTIONS : str
        Interceptions made per match, serialized as ``"interceptions"``.
    DUELS_WON : str
        Duels won per match, serialized as ``"duels_won"``.
    SHOTS_BLOCKED : str
        Shots blocked per match, serialized as ``"shots_blocked"``.
    FOULS : str
        Fouls conceded per match, serialized as ``"fouls"``.
    YELLOW_CARDS : str
        Yellow cards received per match, serialized as ``"yellow_cards"``.
    RED_CARDS : str
        Red cards received per match, serialized as ``"red_cards"``.
    OFFSIDES : str
        Offsides called per match, serialized as ``"offsides"``.
    """

    WIN_SHARE = "win_share", "Wins"
    DRAW_SHARE = "draw_share", "Draws"
    LOSS_SHARE = "loss_share", "Losses"
    GOALS = "goals", "Goals"
    SHOTS = "shots", "Shots"
    SHOTS_ON_TARGET = "shots_on_target", "Shots on target"
    SHOTS_INSIDE_BOX = "shots_inside_box", "Shots inside the box"
    BIG_CHANCES_CREATED = "big_chances_created", "Big chances"
    KEY_PASSES = "key_passes", "Key passes"
    CORNERS = "corners", "Corners"
    POSSESSION = "possession", "Possession"
    PASSES = "passes", "Passes"
    PASS_ACCURACY = "pass_accuracy", "Pass accuracy"
    CROSSES = "crosses", "Crosses"
    CROSS_ACCURACY = "cross_accuracy", "Cross accuracy"
    DRIBBLE_SUCCESS = "dribble_success", "Dribble success"
    SAVES = "saves", "Saves"
    TACKLES = "tackles", "Tackles"
    INTERCEPTIONS = "interceptions", "Interceptions"
    DUELS_WON = "duels_won", "Duels won"
    SHOTS_BLOCKED = "shots_blocked", "Shots blocked"
    FOULS = "fouls", "Fouls"
    YELLOW_CARDS = "yellow_cards", "Yellow cards"
    RED_CARDS = "red_cards", "Red cards"
    OFFSIDES = "offsides", "Offsides"


class FormFamily(models.TextChoices):
    """
    Group a form metric is presented under.

    The grouping is a property of the vocabulary rather than of the interface, so
    the API publishes it and the panel does not have to hold a second copy of the
    same editorial decision.

    Attributes
    ----------
    RESULT : str
        Results and goals, serialized as ``"result"``.
    ATTACKING : str
        Shots and chance creation, serialized as ``"attacking"``.
    POSSESSION : str
        Keeping and moving the ball, serialized as ``"possession"``.
    DEFENDING : str
        Regaining and blocking, serialized as ``"defending"``.
    DISCIPLINE : str
        Fouls, cards, and offsides, serialized as ``"discipline"``.
    """

    RESULT = "result", "Result"
    ATTACKING = "attacking", "Attacking"
    POSSESSION = "possession", "Possession"
    DEFENDING = "defending", "Defending"
    DISCIPLINE = "discipline", "Discipline"
