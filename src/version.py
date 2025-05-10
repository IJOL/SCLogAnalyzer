"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 9
RELEASE = 0
MATURITY = "pyam-exhang"  # "alpha", "beta", or "final"
PATCH = "4480e51"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    # Commits for v0.9.x series
    "339eff6: Enhance leaderboard display: align numeric columns, add totals for kills and deaths, and include last update timestamp",
    "364b342: Add filters for current mode and shard in ConnectedUsersPanel; update log entry handling to include mode",
    "b9aa870: Fix mutex check output: restore stdout before error message for clarity",
    "f7fccd5: Add stdout redirection control: implement environment variable check and enable/disable functions",
    "1b8f86e: Change log level to DEBUG for async Supabase client initialization and authentication success messages",
    "d2caab2: Add test CLI for SCLogAnalyzer with simulated users and RealtimeBridge integration",
    "a388adc: Remove manual authentication token setting in SupabaseManager during async connection",
    "5f205ab: Fix presence synchronization in ConnectedUsersPanel to use 'general' channel",
    "053690b: Refactor RealtimeBridge to use a single 'general' channel for presence and broadcast communication",
    "d88a5ca: Bump version to v0.9.99-d2f2325-pyam-exhang",
    "5708151: Refactor test CLI to support multiprocessing for simulated users and enhance RealtimeBridge integration",
    "4480e51: Enhance RealtimeBridge to track user activity and improve presence synchronization with ping broadcasts",
]
