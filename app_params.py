from bson import ObjectId

model_card = "gpt-3.5-turbo-0125"  # gpt-4-1106-preview

# Removes the brown left menu with list of documents. (Useful to record demo videos, etc.)
NO_LEFT_MENU = False

# The Global Chat can be enabled or disabled
ENABLE_CHAT = True

# The Markers can be enabled or disabled
ENABLE_MARKERS = True

# Local components: Comment & Brainstorm, they can either both be enabled or disabled
ENABLE_LOCAL = True

# The entire Warn, Verify and Auding can be enabled or disabled
ENABLE_WARN_VERIFY_AUDIT = True

# Default markers: can be modifed

DEFAULT_MARKERS = {}
DEFAULT_MARKERS["basic"] = [
    {"id": str(ObjectId()), "name": "Typos", "strike_color": "#E31E3E", "strike_style": "dashed", "description": "Suggest any edits related to spelling, punctuation, grammar, or capitalization.", "visible": "visible"},
    {"id": str(ObjectId()), "name": "Professional", "strike_color": "#e3861c", "strike_style": "solid", "description": "Spot words or phrases that are too informal, and suggest improvements to sound more professional.", "visible": "visible"},
    {"id": str(ObjectId()), "name": "Confidence", "strike_color": "#1ca7e3", "strike_style": "solid", "description": "If there's a part that doesn't sound confident, help improve it.", "visible": "visible"},
]

DEFAULT_MARKERS["simplification"] = [
    {"id": str(ObjectId()), "name": "Typos", "strike_color": "#E31E3E", "strike_style": "dashed", "description": "Suggest any edits related to spelling, punctuation, grammar, or capitalization.", "visible": "visible"},
    {"id": str(ObjectId()), "name": "Lexical Simplification", "strike_color": "#e3861c", "strike_style": "solid", "description": "Propose replacements for any word or phrase that is too complicated to understand by a 10-year-old.", "visible": "visible"},
    {"id": str(ObjectId()), "name": "Sentence Split", "strike_color": "#238b24", "strike_style": "solid", "description": "If a sentence is too long, propose edits that can split the sentence into multiple shorter sentences that can each be understood on their own.", "visible": "visible"},
    {"id": str(ObjectId()), "name": "Elaboration", "strike_color": "#1ca7e3", "strike_style": "solid", "description": "If a concept is complex and might not be understood by a person without background knowledge, suggest elaborations that provide the needed context. For example, you can provide definitions for complex terms, or expand on an abbreviation, or provide a concrete example for a concept.", "visible": "visible"},
    {"id": str(ObjectId()), "name": "Conciseness", "strike_color": "#6b01d5", "strike_style": "solid", "description": "Suggest portions of the document that are not required and that can be deleted or shortened. Examples of things that can be removed or shortened are asides, parenthesis, or in-depth details.", "visible": "visible"}
]

# Default marker type
default_marker_type = "basic"
assert default_marker_type in DEFAULT_MARKERS, "Invalid default marker type"