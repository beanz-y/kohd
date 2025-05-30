# kohd_core/kohd_rules.py

# The 3x3 grid layout of Kohd node names as shown in the PDF [cite: 1199]
# Row 0: ABC, DEF, GHI
# Row 1: JKL, MNO, PQR
# Row 2: STU, VWX, YZ
NODE_LAYOUT = [
    ['ABC', 'DEF', 'GHI'],
    ['JKL', 'MNO', 'PQR'],
    ['STU', 'VWX', 'YZ']
]

# Defines the letters associated with each node
# Based on PDF page 304 [cite: 1199]
NODE_LETTERS = {
    'ABC': ('A', 'B', 'C'),
    'DEF': ('D', 'E', 'F'),
    'GHI': ('G', 'H', 'I'),
    'JKL': ('J', 'K', 'L'),
    'MNO': ('M', 'N', 'O'),
    'PQR': ('P', 'Q', 'R'),
    'STU': ('S', 'T', 'U'),
    'VWX': ('V', 'W', 'X'),
    'YZ':  ('Y', 'Z', None)  # YZ node only has Y and Z
}

# Main mapping for each English letter to its node name and subnode count
# Subnode count: 1 for 1st letter, 2 for 2nd, 3 for 3rd in the node's tuple
# Based on PDF page 304 construction steps 1-3 [cite: 1200, 1203, 1206]
LETTER_TO_NODE_INFO = {}
for node_name, letters_in_node in NODE_LETTERS.items():
    for i, letter in enumerate(letters_in_node):
        if letter:  # Ensure 'None' for the 3rd position in 'YZ' isn't processed
            LETTER_TO_NODE_INFO[letter] = {
                'node_name': node_name,
                'subnodes': i + 1
            }

# Predefined conceptual coordinates for the center of each node on a grid.
# These can be scaled by the canvas widget later.
# Using a 300x300 conceptual grid for now, with (0,0) at top-left.
# Spacing of 100 units between nodes, starting at 50.
# (x, y)
NODE_POSITIONS = {
    'ABC': (50, 50),   'DEF': (150, 50),  'GHI': (250, 50),
    'JKL': (50, 150),  'MNO': (150, 150), 'PQR': (250, 150),
    'STU': (50, 250),  'VWX': (150, 250), 'YZ':  (250, 250)
}

# Lexicon for simplified, non-nodally constructed forms (PDF page 306) [cite: 1219, 1220, 1221]
# The 'glyph_type' can be used by the drawing engine to know how to render them.
# Specific drawing routines will be needed for each type.
LEXICON_GLYPHS = {
    "AND":          {'glyph_type': 'AND', 'text': "And"},
    "OR":           {'glyph_type': 'OR', 'text': "Or"},
    "TRUE_IS":      {'glyph_type': 'TRUE_IS', 'text': "True. Is."},
    "FALSE_NOT":    {'glyph_type': 'FALSE_NOT', 'text': "False. Not."},
    "BECAUSE_SINCE":{'glyph_type': 'BECAUSE_SINCE', 'text': "Because. Since."},
    "SO_THIS_CAUSING": {'glyph_type': 'SO_THIS_CAUSING', 'text': "So. This. Causing."},
    "IF":           {'glyph_type': 'IF', 'text': "If"},
    "IF_THEN":      {'glyph_type': 'IF_THEN', 'text': "If-Then"}, # Placed between two glyphs
    "THERE_IS":     {'glyph_type': 'THERE_IS', 'text': "There is. There exists."},
    "UNIQUE_EXISTS_ONE": {'glyph_type': 'UNIQUE_EXISTS_ONE', 'text': "Unique. There exists exactly one."},
    "FROM_TO":      {'glyph_type': 'FROM_TO', 'text': "From-to. Transition."}, # Placed between two glyphs
    # Pronouns (glyph_type needs to map to a specific drawing routine for each)
    # Based on clarification: glyphs are to the left of the words on PDF page 306 [cite: 1221]
    "I_ME":         {'glyph_type': 'PRONOUN_I_ME', 'text': "I/Me"},
    "YOU_SINGULAR": {'glyph_type': 'PRONOUN_YOU_SINGULAR', 'text': "You"},
    "THEM_SINGULAR":{'glyph_type': 'PRONOUN_THEM_SINGULAR', 'text': "Them <singular>"},
    "WE":           {'glyph_type': 'PRONOUN_WE', 'text': "We"},
    "YOU_PLURAL":   {'glyph_type': 'PRONOUN_YOU_PLURAL', 'text': "You All"},
    "THEM_PLURAL":  {'glyph_type': 'PRONOUN_THEM_PLURAL', 'text': "Them <plural>"},
    "THEIR_THEIRS_SINGULAR": {'glyph_type': 'PRONOUN_THEIR_THEIRS_SINGULAR', 'text': "Their/Theirs <singular>"},
    "THEIR_THEIRS_PLURAL":   {'glyph_type': 'PRONOUN_THEIR_THEIRS_PLURAL', 'text': "Their/Theirs <plural>"},
}

# Articles modify the charge node (PDF page 306) [cite: 1225, 1226]
ARTICLE_GLYPHS = {
    "THE": {'glyph_type': 'ARTICLE_THE', 'text': "The <definite>"}, # Theta-like symbol
    "A":   {'glyph_type': 'ARTICLE_A', 'text': "A <indefinite>"}    # Circle with plus
}

# --- Constants for Drawing Logic (can be expanded) ---
# Subnode representation (e.g., dot radius)
SUBNODE_RADIUS = 3
# Ring node representation (e.g., offset from parent node edge)
RING_NODE_INSET_FACTOR = 0.7 # Ring radius is 70% of parent node radius

# Null Modifier (PDF page 305) [cite: 1215]
NULL_MODIFIER_GLYPH_TYPE = 'NULL_MODIFIER'

# Punctuation (PDF page 307) [cite: 1231]
PUNCTUATION_GLYPH_TYPES = {
    '.': 'PERIOD',
    '!': 'EXCLAMATION',
    '?': 'QUESTION',
    ',': 'COMMA' # Comma intersects a trace between words
}

# Coupler (PDF page 306) [cite: 1222]
COUPLER_GLYPH_TYPE = 'COUPLER'

if __name__ == '__main__':
    # Quick test to ensure mappings are generated correctly
    print("--- LETTER_TO_NODE_INFO ---")
    for letter, info in sorted(LETTER_TO_NODE_INFO.items()):
        print(f"Letter: {letter}, Node: {info['node_name']}, Subnodes: {info['subnodes']}")

    print("\n--- NODE_POSITIONS ---")
    for node_name, pos in NODE_POSITIONS.items():
        print(f"Node: {node_name}, Position: {pos}")

    print("\n--- Sanity Check: 'M', 'O', 'T', 'Y', 'Z' ---")
    if 'M' in LETTER_TO_NODE_INFO:
        print(f"M: {LETTER_TO_NODE_INFO['M']}")
    if 'O' in LETTER_TO_NODE_INFO:
        print(f"O: {LETTER_TO_NODE_INFO['O']}")
    if 'T' in LETTER_TO_NODE_INFO:
        print(f"T: {LETTER_TO_NODE_INFO['T']}")
    if 'Y' in LETTER_TO_NODE_INFO:
        print(f"Y: {LETTER_TO_NODE_INFO['Y']}")
    if 'Z' in LETTER_TO_NODE_INFO:
        print(f"Z: {LETTER_TO_NODE_INFO['Z']}")
    if 'NONE_TEST' not in LETTER_TO_NODE_INFO.get('YZ', {}).get('letters', []): # Should not exist
        pass

    print("\n--- LEXICON_GLYPHS ---")
    for key, val in LEXICON_GLYPHS.items():
        print(f"{key}: {val}")

    print("\n--- ARTICLE_GLYPHS ---")
    for key, val in ARTICLE_GLYPHS.items():
        print(f"{key}: {val}")