from .imap_importer import (
    ensure_mail_schema,
    get_account,
    get_message,
    list_accounts,
    list_messages,
    load_secret,
    save_account,
    store_secret,
    sync_account,
)
from .postfach_imap import sync_account as postfach_sync_account
from .postfach_smtp import send_draft as postfach_send_draft
from .postfach_store import (
    create_account as postfach_create_account,
)
from .postfach_store import (
    create_draft as postfach_create_draft,
)
from .postfach_store import (
    create_followup_task as postfach_create_followup_task,
)
from .postfach_store import (
    ensure_postfach_schema,
)
from .postfach_store import (
    extract_structured as postfach_extract_structured,
)
from .postfach_store import (
    get_account as postfach_get_account,
)
from .postfach_store import (
    get_draft as postfach_get_draft,
)
from .postfach_store import (
    get_thread as postfach_get_thread,
)
from .postfach_store import (
    link_entities as postfach_link_entities,
)
from .postfach_store import (
    list_accounts as postfach_list_accounts,
)
from .postfach_store import (
    list_drafts_for_thread as postfach_list_drafts_for_thread,
)
from .postfach_store import (
    list_threads as postfach_list_threads,
)

__all__ = [
    "ensure_mail_schema",
    "get_account",
    "get_message",
    "load_secret",
    "list_accounts",
    "list_messages",
    "save_account",
    "store_secret",
    "sync_account",
    "ensure_postfach_schema",
    "postfach_create_account",
    "postfach_get_account",
    "postfach_list_accounts",
    "postfach_sync_account",
    "postfach_get_thread",
    "postfach_list_threads",
    "postfach_create_draft",
    "postfach_get_draft",
    "postfach_send_draft",
    "postfach_link_entities",
    "postfach_extract_structured",
    "postfach_create_followup_task",
    "postfach_list_drafts_for_thread",
]
