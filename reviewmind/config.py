"""Project configuration constants.

OPENAI_API_KEY authenticates OpenAI API requests.
GITHUB_TOKEN authenticates GitHub API requests and repository writes.
GITHUB_WEBHOOK_SECRET verifies webhook payload signatures.
PORT controls the Flask server port.
MODEL selects the OpenAI model for reviews and style writing.
MAX_SUGGESTIONS caps review suggestions per PR.
MIN_FEEDBACK_FOR_STYLE controls when TEAM_STYLE.md is generated.
FIX_BRANCH_PREFIX prefixes automated fix branches.
STYLE_FILE_NAME names the committed style guide.
MAX_ACCEPTED_EXAMPLES limits accepted examples in prompts.
MAX_REJECTED_EXAMPLES limits rejected examples in prompts.
DB_PATH identifies the SQLite database file.
"""

import os

from dotenv import load_dotenv


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", 5000))

MODEL = "gpt-4o-mini"
MAX_SUGGESTIONS = 5
MIN_FEEDBACK_FOR_STYLE = 20
FIX_BRANCH_PREFIX = "reviewmind/fix-pr-"
STYLE_FILE_NAME = "TEAM_STYLE.md"
MAX_ACCEPTED_EXAMPLES = 10
MAX_REJECTED_EXAMPLES = 5
DB_PATH = "reviewmind.db"
