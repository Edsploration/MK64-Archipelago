from typing import TYPE_CHECKING
from dataclasses import dataclass

from . import Locations
from Options import Choice, DefaultOnToggle, Toggle, Range, OptionList, StartInventoryPool, PerGameCommonOptions, \
    NamedRange

if TYPE_CHECKING:
    from . import MK64World


class TwoPlayer(Toggle):
    """(NOT YET SUPPORTED)
    Start with two characters unlocked and shuffle a separate Player 2 set of item powers into the item pool.

    This is the intended way to do local multiplayer, but you can still access the 2-player grand prix mode
    with this off, and the 1-player grand prix mode with it on."""
    display_name = "Two Player Couch Co-op"


class GameMode(Choice):
    """Determines how to advance through the game. Cups is closest to the vanilla game.

    Cups: Courses are raced in sets of four, place 4th or better to advance each race. Unlock each cup progressively.
    The Cups victory condition is beating the Special Cup on 150cc.

    Courses (NOT YET SUPPORTED): Each course is run individually. Unlock the final courses progressively to reach the
    final race. The Courses victory condition is winning 1st place on the last course."""
    display_name = "Game Mode"
    option_cups = 0
    option_courses = 1
    default = 0


class Goal(Choice):
    """Determines the victory condition.

    Final Win: Victory is placed at Special Cup 150cc Gold on Cups Mode, or 1st on the last course on Courses Mode
    All Wins: Victory requires 150cc Gold on all cups on Cups Mode, or 1st on all courses on Courses Mode"""
    display_name = "Goal"
    option_final_win = 0
    option_all_wins = 1
    default = 0


class LogicDifficulty(Choice):
    """Scales the logic threshhold where skill is involved. Specifically, how many good items are available before you
    are expected to be able to qualify and win on tough courses.

    Basic: Makes sure you have plenty of good items early. For easier play, or skipping 50 cc.
    (Basic is more likely to fail generation. To raise chances try increasing shuffle_item_box_clusters and
    minimum_filler_items. Future versions will be less fragile to generation failure.)

    Advanced: Balanced runs for a competent karter.

    Expert: Low logic, high randomness, high skill. Few good items may be available early in the run.

    No Logic: If fences are enabled, THE RUN MAY BE NEAR IMPOSSIBLE!"""
    display_name = "Logic Difficulty"
    option_basic = 6
    option_advanced = 3
    option_expert = 0
    option_no_logic = -100
    default = 6


class LockedCourses(Range):
    """(NOT YET SUPPORTED)
    In Courses Game Mode, how many final courses are locked until Progressive Course Unlock items are found."""
    display_name = "Locked Courses"
    range_start = 0
    range_end = 15
    default = 4


class CourseOrder(Choice):
    """The order for the courses to be arranged in."""
    display_name = "Course Order"
    option_vanilla = 0
    option_shuffle = 1
    option_short_to_long = 2
    option_long_to_short = 3
    option_alphabetical = 4
    default = 1


class FinalCoursePool(OptionList):
    """When Course Order is set to shuffle, the final course will be chosen from the Final Course Pool.
    Leaving this blank will allow any course to come last.

    For Rainbow Road to come last use: ["Rainbow Road"].

    For Bowser's Castle to come last use: ["Bowser's Castle"].

    For any course longer than 1000 meters to come last use: ["Rainbow Road", "Wario Stadium", "Toad's Turnpike"]."""
    display_name = "Final Course Pool"
    valid_keys = frozenset({course_name.casefold() for course_name in Locations.course_locations.keys()})
    valid_keys_casefold = True


class MirrorCourseChance(Range):
    """(NOT YET SUPPORTED) Percent chance for a course to be mirrored."""
    display_name = "Mirror Course Chance"
    range_start = 0
    range_end = 100
    default = 0


class TwoLapCourses(Choice):
    """Reduce the number of laps in a race from 3 to 2 on long courses."""
    display_name = "Two Lap Courses"
    option_off = 0
    option_rainbow_road = 1
    option_wario_stadium = 2
    option_rainbow_road_and_wario_stadium = 3
    default = 0


class CupTrophyLocations(Choice):
    """Which sets of trophies are used as location checks. Finishing a cup will reward items for that trophy and engine
    class, and all below. For example, getting 100cc Silver will also give 100cc Bronze, 50cc Silver, and 50cc Bronze.

    ▃ Three: Bronze, Silver, and Gold (any engine class)
    ▞ Three Scaling: Bronze, 100cc Silver, 150cc Gold
    ▟ Five: Bronze, Silver, and Gold, 100cc Gold, 150cc Gold
    ▟ Six: Bronze, Silver, and Gold, 100cc Silver, 100cc Gold, 150cc Gold
    █ Nine: All three trophies in all three engine classes"""
    display_name = "Cup Trophy Locations"
    option_three = 0b0001
    option_three_scaling = 0b0010
    option_five = 0b0101
    option_six = 0b0111
    option_nine = 0b1111
    default = 0b0101


class HazardLocations(DefaultOnToggle):
    """Whether to include hazards which can be destroyed or defeated by the star power as location checks."""
    display_name = "Add Hazard Locations"


class SecretLocations(DefaultOnToggle):
    """Whether to add 10 location checks as item pickups in noteworthy locations on certain courses."""
    display_name = "Add Course Secret Locations"


class ShuffleDriftAbilities(Choice):
    """Optionally shuffle into the item pool the ability to drift and the ability to use mini-turbos as progressive
    unlocks per kart. "Plentiful" shuffles a 3rd progressive unlock into the pool. "Free Drift" means karts start
    with the ability to drift. "Free mini-turbo" means both abilities will be obtained together."""
    display_name = "Shuffle Drift Abilities"
    option_off = 0
    option_on = 1
    option_plentiful = 2
    option_free_drift = 3
    option_free_mini_turbo = 4
    alias_vanilla = 0
    alias_shuffle = 0
    alias_false = 0
    alias_on = 1
    alias_yes = 1
    alias_true = 1
    default = 1


class TractionTires(DefaultOnToggle):
    """Optionally shuffle into the item pool the ability to have traction on off-road and winter surface types,
    per kart. "Off" means karts always have traction, as in the vanilla game."""
    display_name = "Add Traction Tires"


class StartingItems(DefaultOnToggle):
    """Optionally shuffle into the item pool a random item power to start each race with, per kart. For example
    Mario may be able to start each race with a blue shell. Which item is random per kart."""
    display_name = "Add Starting Items"


class ShuffleRailings(DefaultOnToggle):
    """Whether to shuffle most track railings into the item pool."""
    display_name = "Shuffle Railings"


class Fences(DefaultOnToggle):
    """Adds colored fences to every course to add variety to the player's racing lines, and blocks about 20% of
    item boxes. Also adds Yellow/Red/Green/Blue Switch items to the item pool which disable that color of fences.
    Fences only affect player karts; shells and CPU karts path through them."""
    display_name = "Fences Block Paths"


class FeatherItem(DefaultOnToggle):
    """Adds the feather item as seen in Super Mario Kart and the early demos of Mario Kart 64. It can be used to vault
    fences. Having access to the feather puts locations blocked by fences in logic."""
    display_name = "Feather Item"


class ShuffleItemBoxRespawning(Toggle):
    """Causes item boxes to not respawn mid-race, and shuffles one "item box respawning" item into the item pool."""
    display_name = "Shuffle Item Box Respawning"


class ConsistentItemBoxes(Choice):
    """Make each item box always give the same item. "On" will always show which item will be given instead of a
    question mark (?) inside the item boxes. "Identify" will only show which item will be given after triggering the
    item roulette once."""
    display_name = "Consistent Item Boxes"
    option_off = 0
    option_on = 1
    option_identify = 2
    default = 0


class ShuffleSpecialItemBoxes(DefaultOnToggle):
    """Whether to shuffle the special item boxes which always give blue shells into the item pool. One is attached to
    the hot air balloon on Luigi Raceway, and the other is on the big rock on Koopa Troopa Beach."""
    display_name = "Shuffle Special Item Boxes"


class ShuffleItemBoxClusters(Range):
    """How many item box clusters to shuffle into the item pool. At least one item spot from each shuffled cluster will
    be used as a location check.
    (More shuffled clusters helps generation succeed. Future versions will be less fragile to generation failure.)"""
    display_name = "Shuffle Item Box Clusters"
    range_start = 0
    range_end = 72
    default = 36


class FillerTrapPercentage(Range):
    """What percentage of filler items will be traps."""
    display_name = "Filler Trap Percentage"
    range_start = 0
    range_end = 100
    default = 10


class MinimumFillerItems(Range):
    """Force more filler items than needed to match the number of locations.
    (More filler items helps generation succeed. Future versions will be less fragile to generation failure.)"""
    display_name = "Minimum Filler Items"
    range_start = 0
    range_end = 60
    default = 30


class LowEngineClass(NamedRange):
    """Adjust the 50cc engine class. Capped 25cc below the Middle Engine Class.

    Below Middle Random: A flat random distribution from 35cc to 25cc below Middle Engine Class.

    Can be changed later with /low_engine_class [value]"""
    display_name = "Low Engine Class"
    range_start = 35
    range_end = 150
    default = 50
    special_range_names = {
        "random_below_middle": 0
    }


class MiddleEngineClass(NamedRange):
    """Adjust the 100cc engine class.

    Can be changed later with /middle_engine_class [value]"""
    display_name = "Middle Engine Class"
    range_start = 60
    range_end = 175
    default = 100


class HighEngineClass(NamedRange):
    """Adjust the 150cc engine class. Capped 25cc above the Middle Engine Class.

    Above Middle Random: A flat random distribution from 25cc above the Middle Engine Class to 200cc.

    Can be changed later with /high_engine_class [value]"""
    display_name = "High Engine Class"
    range_start = 85
    range_end = 200
    default = 150
    special_range_names = {
        "random_above_middle": 0
    }


class FixResultsMusic(DefaultOnToggle):
    """Fixes the race win results screen music so the first section repeats 2 times, not 64 times.
    The official soundtrack uses this AABB form."""
    display_name = "Fix Winning Results Music"


class SoundMode(Choice):
    """Sets the sound mode in the game's option menu ahead of time."""
    display_name = "Sound Mode"
    option_stereo = 0
    option_headphones = 1
    option_mono = 3
    default = 0


# Options as they will appear in YAML settings
@dataclass
class MK64Options(PerGameCommonOptions):
    start_inventory_from_pool: StartInventoryPool
    two_player: TwoPlayer
    game_mode: GameMode
    goal: Goal
    locked_courses: LockedCourses
    course_order: CourseOrder
    logic_difficulty: LogicDifficulty
    final_course_pool: FinalCoursePool
    mirror_course_chance: MirrorCourseChance
    two_lap_courses: TwoLapCourses
    cup_trophy_locations: CupTrophyLocations
    hazard_locations: HazardLocations
    secret_locations: SecretLocations
    shuffle_drift_abilities: ShuffleDriftAbilities
    add_traction_tires: TractionTires
    add_starting_items: StartingItems
    shuffle_railings: ShuffleRailings
    fences: Fences
    feather_item: FeatherItem
    shuffle_item_box_respawning: ShuffleItemBoxRespawning
    consistent_item_boxes: ConsistentItemBoxes
    shuffle_special_item_boxes: ShuffleSpecialItemBoxes
    shuffle_item_box_clusters: ShuffleItemBoxClusters
    filler_trap_percentage: FillerTrapPercentage
    minimum_filler_items: MinimumFillerItems
    low_engine_class: LowEngineClass
    middle_engine_class: MiddleEngineClass
    high_engine_class: HighEngineClass
    fix_results_music: FixResultsMusic
    sound_mode: SoundMode


# Used for shorthand/faster access to relevant options during world generation
class Opt:
    def __init__(self, world: "MK64World"):
        # Relevant Options
        self.two_player =      world.options.two_player.value
        self.mode =            world.options.game_mode.value
        self.goal =            world.options.goal.value
        self.course_order =    world.options.course_order.value
        self.locked_courses =  world.options.locked_courses.value
        self.logic =           world.options.logic_difficulty.value
        self.final_pool =      world.options.final_course_pool.value
        self.mirror_chance =   world.options.mirror_course_chance.value
        self.two_lap_courses = world.options.two_lap_courses.value
        self.trophies =        world.options.cup_trophy_locations.value
        self.hazards =         world.options.hazard_locations.value
        self.secrets =         world.options.secret_locations.value
        self.drift =           world.options.shuffle_drift_abilities.value
        self.traction =        world.options.add_traction_tires.value
        self.starting_items =  world.options.add_starting_items.value
        self.railings =        world.options.shuffle_railings.value
        self.fences =          world.options.fences.value
        self.feather =         world.options.feather_item.value
        self.box_respawning =  world.options.shuffle_item_box_respawning.value
        self.consistent =      world.options.consistent_item_boxes.value
        self.special_boxes =   world.options.shuffle_special_item_boxes.value
        self.clusters =        world.options.shuffle_item_box_clusters.value
        self.trap_percentage = world.options.filler_trap_percentage.value
        self.min_filler =      world.options.minimum_filler_items.value
        self.low_engine =      world.options.low_engine_class.value
        self.middle_engine =   world.options.middle_engine_class.value
        self.high_engine =     world.options.high_engine_class.value
        self.fix_music =       world.options.fix_results_music.value
        self.sound_mode =      world.options.sound_mode.value
