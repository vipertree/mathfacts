"""
Visual theme registry. Adding a theme = one entry here + one CSS file at
static/drill/themes/<key>.css (custom-property overrides; see pirate.css).

Optional image slots (all gracefully absent; the app ships on CSS + emoji):
    static/drill/themes/<key>/background.webp   full-page backdrop
    static/drill/themes/<key>/mascot.webp       replaces the mascot emoji
"""

THEMES = {
    'pirate': {
        'name': 'Pirate',
        'greeting': 'Ahoy',
        'icon': '🏴‍☠️',
        'mascot': '🦜',
        'points_name': 'gold coins',
        'point_icon': '🪙',
        'cheers': ['Arr, well done!', 'Treasure found!', 'Shiver me timbers!',
                   'Aye aye, matey!', 'X marks the spot!'],
        'oops': ["Walk it back, matey…", 'Even captains miss a wave.'],
        'goal_met': "Ye plundered today's treasure! 🏆",
        'practice_label': 'Set sail!',
        'instructions_title': '🏴‍☠️ How to be a Math Pirate',
        'instructions_intro': ('Answer math facts to fill your treasure chest! '
                               'Earn {goal} 🪙 gold coins a day to keep your streak alive.'),
    },
    'hightech': {
        'name': 'High Tech',
        'greeting': 'Greetings',
        'icon': '🛰️',
        'mascot': '🤖',
        'points_name': 'energy cells',
        'point_icon': '🔋',
        'cheers': ['Systems optimal!', 'Upload complete!', 'Calculation verified!',
                   'Power surge!', 'Circuits firing!'],
        'oops': ['Recalibrating…', 'Glitch detected. Rerouting.'],
        'goal_met': 'Daily mission complete! 🚀',
        'practice_label': 'Launch!',
        'instructions_title': '🛰️ Mission Briefing',
        'instructions_intro': ('Solve equations to power up your core! '
                               'Collect {goal} 🔋 energy cells a day to keep your streak online.'),
    },
    'princess': {
        'name': 'Princess',
        'greeting': 'Welcome',
        'icon': '👑',
        'mascot': '🦄',
        'points_name': 'jewels',
        'point_icon': '💎',
        'cheers': ['Royally done!', 'Simply majestic!', 'A sparkling answer!',
                   'The kingdom cheers!', 'Crown-worthy!'],
        'oops': ['Every royal practices…', 'The castle believes in you.'],
        'goal_met': 'The royal quest is complete! 🏰',
        'practice_label': 'Begin the quest!',
        'instructions_title': '👑 Your Royal Guide',
        'instructions_intro': ('Solve math facts to fill your crown with sparkle! '
                               'Collect {goal} 💎 jewels a day to keep your streak shining.'),
    },
    'dinosaur': {
        'name': 'Dinosaur',
        'greeting': 'Rawr',
        'icon': '🦖',
        'mascot': '🦕',
        'points_name': 'amber pieces',
        'point_icon': '🟠',
        'cheers': ['Roarsome!', 'Dino-mite!', 'Stomp on!', 'Fossil found!',
                   'Mighty work!'],
        'oops': ['Even a T-rex trips…', 'Try that track again.'],
        'goal_met': 'You dug up all the amber today! 🏆',
        'practice_label': 'Start the stomp!',
        'instructions_title': '🦖 How to be a Math Dino',
        'instructions_intro': ('Solve math facts to dig up shiny amber! '
                               'Collect {goal} 🟠 amber pieces a day to keep '
                               'your streak stomping.'),
    },
    'deepsea': {
        'name': 'Deep Sea',
        'greeting': 'Dive in',
        'icon': '🌊',
        'mascot': '🐙',
        'points_name': 'pearls',
        'point_icon': '🫧',
        'cheers': ['Making waves!', 'Deep thinking!', 'Ten tentacles up!',
                   'Current-ly perfect!', 'Pearl found!'],
        'oops': ['Let that one drift by…', 'Even octopuses get tangled.'],
        'goal_met': "Today's pearls are all collected! 🏆",
        'practice_label': 'Dive down!',
        'instructions_title': '🌊 Your Deep-Sea Guide',
        'instructions_intro': ('Answer math facts to gather pearls from the '
                               'deep! Collect {goal} 🫧 pearls a day to keep '
                               'your streak afloat.'),
    },
    'space': {
        'name': 'Space Cadet',
        'greeting': 'Welcome aboard',
        'icon': '🚀',
        'mascot': '👽',
        'points_name': 'star charts',
        'point_icon': '⭐',
        'cheers': ['Stellar!', 'Orbit achieved!', 'Cosmic!', 'Full thrust!',
                   'Star mapped!'],
        'oops': ['Course correction…', 'Even comets wobble.'],
        'goal_met': "Today's star chart is complete! 🏆",
        'practice_label': 'Blast off!',
        'instructions_title': '🚀 Cadet Training',
        'instructions_intro': ('Solve math facts to chart the stars! '
                               'Collect {goal} ⭐ star charts a day to keep '
                               'your streak in orbit.'),
    },
    'bakery': {
        'name': 'Bakery',
        'greeting': 'Good morning',
        'icon': '🥐',
        'mascot': '🧁',
        'points_name': 'sprinkles',
        'point_icon': '🍩',
        'cheers': ['Sweet!', "Baker's dozen!", 'Piping hot!', 'Perfectly risen!',
                   'Icing on top!'],
        'oops': ['Every baker burns one…', 'Let that batch cool.'],
        'goal_met': "Today's batch is all frosted! 🏆",
        'practice_label': 'Start baking!',
        'instructions_title': '🧁 Your Baking Guide',
        'instructions_intro': ('Solve math facts to earn sprinkles for your '
                               'cakes! Collect {goal} 🍩 sprinkles a day to '
                               'keep your streak rising.'),
    },
    'jungle': {
        'name': 'Jungle Explorer',
        'greeting': 'Onward',
        'icon': '🧭',
        'mascot': '🐒',
        'points_name': 'bananas',
        'point_icon': '🍌',
        'cheers': ['Vine work!', 'Trail blazed!', 'Swing on!', 'Well spotted!',
                   'Path found!'],
        'oops': ['Backtrack a little…', 'Even monkeys miss a vine.'],
        'goal_met': "Today's trail is fully mapped! 🏆",
        'practice_label': 'Head out!',
        'instructions_title': '🧭 Explorer Field Guide',
        'instructions_intro': ('Answer math facts to gather bananas on the '
                               'trail! Collect {goal} 🍌 bananas a day to keep '
                               'your streak swinging.'),
    },
}

DEFAULT_THEME = 'pirate'


def get_theme(key):
    return THEMES.get(key, THEMES[DEFAULT_THEME])
