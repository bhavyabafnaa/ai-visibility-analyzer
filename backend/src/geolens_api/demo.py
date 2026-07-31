"""Deterministic local demo configuration shared by the seed script and mock provider."""

DEMO_PROJECT_NAME = "Acme Cloud"
DEMO_PROJECT_ALIASES = ["Acme", "AcmeCloud"]
DEMO_SITE_URL = "https://acme.example"
DEMO_COMPETITORS = [
    {
        "name": "Northstar AI",
        "url": "https://northstar.example",
        "aliases": ["Northstar"],
    },
    {
        "name": "Summit Search",
        "url": "https://summit.example",
        "aliases": ["Summit"],
    },
]
DEMO_PROMPTS = [
    "What are the best AI visibility platforms for B2B teams?",
    "Compare Acme Cloud with Northstar AI for citation monitoring.",
    "Which tools help marketing teams track brand mentions in AI answers?",
    "What should an enterprise look for in a generative search analytics platform?",
]
