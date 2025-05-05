"""Version information for SC Log Analyzer"""

MAJOR = 0
MINOR = 7
RELEASE = 0
MATURITY = "checkmate"  # "alpha", "beta", or "final"
PATCH = "003cdfc"

VERSION = f"v{MAJOR}.{MINOR}.{RELEASE}-{PATCH}-{MATURITY}"

def get_version():
    """Return the full version string"""
    return VERSION


# Recent commit messages
COMMIT_MESSAGES = [
    "003cdfc: Refactor tab creation methods to include complete tab configuration information and improve dynamic tab handling",
    "867d2b3: Fix indentation for wx.CallAfter in LogAnalyzerFrame to ensure proper update checks",
    "fb9f144: Add view existence check for Supabase tabs and skip dynamic view creation in non-debug mode",
    "8edadc6: Add dynamic tab support for user weapons and zones in configuration and enhance SupabaseDataProvider with column existence check",
    "268461b: Ensure dynamic views exist for Supabase when tabs configuration changes",
    "a98f8a7: Add dynamic tabs configuration grid to ConfigDialog",
    "9a0ec97: Add dynamic tab support and view management in SupabaseDataProvider and DataDisplayManager",
    "db290db: Implementar get_metadata con sistema de cachÃ©",
    "b98a84b: Remove delayed update check from startup in LogAnalyzerFrame",
    "4e0707a: Add checks for table existence before querying and creating Resumen view in SupabaseDataProvider",
    "4180fe0: Emit message bus event for datasource change instead of using handle_datasource_change method",
    "5adc12a: Refactor datasource change handling and integrate Supabase onboarding process",
    "0ab87a1: Enhance Supabase onboarding with retry logic for list_tables function availability and add force reconnection option in SupabaseManager",
    "210f696: Enhance Supabase onboarding by detecting datasource and key changes in configuration",
    "33b79a0: Add pyperclip for clipboard operations in Supabase onboarding",
    "db1e623: Implement Supabase onboarding process for datasource switch and add related message bus notifications",
    "e61d748: Remove unused generate_hash function from supbase_functions.sql",
]
