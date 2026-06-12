"""
Visual theme registry. Adding a theme = one entry here + one CSS file at
static/drill/themes/<key>.css (custom-property overrides; see pirate.css).

Optional image slots (all gracefully absent — the app ships on CSS + emoji):
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
        'oops': ['Recalibrating…', 'Glitch detected — rerouting.'],
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
}

DEFAULT_THEME = 'pirate'


def get_theme(key):
    return THEMES.get(key, THEMES[DEFAULT_THEME])
