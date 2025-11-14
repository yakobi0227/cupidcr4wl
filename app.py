"""Flask application that exposes the cupidcr4wl search as a web interface."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from flask import Flask, render_template, request

from search_core import load_user_agents, load_websites, search_targets

BASE_DIR = Path(__file__).resolve().parent
USER_AGENT_FILE = BASE_DIR / "user_agents.txt"
USERNAME_SITE_FILE = BASE_DIR / "usernames.json"
PHONE_SITE_FILE = BASE_DIR / "phonenumbers.json"

app = Flask(__name__)


def _load_user_agents() -> List[str]:
    if not USER_AGENT_FILE.exists():
        raise FileNotFoundError(
            "user_agents.txt is required to run the web application."
        )
    return load_user_agents(str(USER_AGENT_FILE))


USER_AGENTS: Optional[List[str]] = None


def get_user_agents() -> List[str]:
    global USER_AGENTS
    if USER_AGENTS is None:
        USER_AGENTS = _load_user_agents()
    return USER_AGENTS


@app.route("/", methods=["GET", "POST"])
def index():
    errors: List[str] = []
    results = None
    query_text = ""
    query_type = request.form.get("query_type", "username")
    debug = request.form.get("debug") == "on"

    if request.method == "POST":
        query_text = request.form.get("query", "").strip()
        if not query_text:
            errors.append("Please enter at least one username or phone number.")
        else:
            targets = [part.strip() for part in query_text.split(",") if part.strip()]
            if not targets:
                errors.append("No valid targets were supplied after splitting on commas.")
            else:
                site_file = USERNAME_SITE_FILE if query_type == "username" else PHONE_SITE_FILE
                if not site_file.exists():
                    errors.append(f"The configuration file '{site_file.name}' is missing.")
                else:
                    try:
                        websites = load_websites(str(site_file))
                        results = search_targets(
                            targets,
                            user_agents=get_user_agents(),
                            websites_by_category=websites,
                            debug=debug,
                        )
                    except ValueError as exc:
                        errors.append(str(exc))
                    except FileNotFoundError as exc:
                        errors.append(str(exc))

    return render_template(
        "index.html",
        results=results,
        errors=errors,
        query_text=query_text,
        query_type=query_type,
        debug=debug,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
