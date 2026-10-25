"""PC IM read state from public IM.16f88554.js / index.a9f61821.js.

_reportMarkRead runs after clearUnread(target). Single-chat totals exclude
all groups; mute total is explicitly fixed to zero by the web implementation.
"""

GLOBAL_COUNTERS = (
    'chat_total_unread_count',
    'mute_chat_total_unread_count',
    'stranger_total_unread_count',
)


def nonnegative_integer(value, error):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value and value.isascii() and value.isdigit():
        return int(value)
    raise ValueError(error)


def global_counters(values):
    if not isinstance(values, dict) or set(values) != set(GLOBAL_COUNTERS):
        raise ValueError('READ_GLOBAL_STATE_MISSING')
    return {key: nonnegative_integer(values[key], 'READ_GLOBAL_STATE_INVALID')
            for key in GLOBAL_COUNTERS}


def chat_id(chat):
    if not isinstance(chat, dict):
        raise ValueError('READ_CHAT_STATE_INVALID')
    value = chat.get('chat_user_id', chat.get('chat_id'))
    if not isinstance(value, str) or not value or value.startswith('group:'):
        raise ValueError('READ_CHAT_STATE_INVALID')
    return value


def chat_type(chat):
    info = chat.get('info')
    if not isinstance(info, dict) or any(type(info.get(key)) is not bool
                                         for key in ('is_friend', 'is_mute')):
        raise ValueError('READ_CHAT_CATEGORY_UNKNOWN')
    # ChatRepository maps info.isFriend === false to isStranger; stranger wins.
    return 2 if not info['is_friend'] else 1 if info['is_mute'] else 0


def chat_page(response, page, collected):
    """Validate page metadata; never interpret missing flags as end-of-list.

    Return entries and whether this is a proven final page. Multiple supplied
    completion signals must agree. Bounded caller rejects unfinished paging.
    """
    data = response.get('data')
    if not isinstance(data, dict):
        raise ValueError('READ_CHAT_LIST_INVALID')
    entries = data.get('chat_list', data.get('chats'))
    if not isinstance(entries, list):
        raise ValueError('READ_CHAT_LIST_INVALID')
    if 'page' in data and nonnegative_integer(data['page'], 'READ_PAGINATION_INVALID') != page:
        raise ValueError('READ_PAGINATION_INVALID')
    signals = []
    if 'has_more' in data:
        if type(data['has_more']) is not bool:
            raise ValueError('READ_PAGINATION_INVALID')
        signals.append(not data['has_more'])
    if 'total' in data:
        total = nonnegative_integer(data['total'], 'READ_PAGINATION_INVALID')
        if collected + len(entries) > total:
            raise ValueError('READ_PAGINATION_INVALID')
        signals.append(collected + len(entries) == total)
    if 'next_ts' in data:
        value = data['next_ts']
        if type(value) is not int or value < -1:
            raise ValueError('READ_PAGINATION_INVALID')
        signals.append(value == -1)
    if not signals or len(set(signals)) != 1 or (not entries and not signals[0]):
        raise ValueError('READ_PAGINATION_INCOMPLETE')
    return entries, signals[0]


def read_state(chat, conversation, unread_response, counters=None, *, chats=None):
    """Build exactly one target acknowledgement without modifying other chats.

    Explicit counters remain assertions only, never overrides. Zero unread
    still acknowledges maxStoreId and removes offline state, like the website.
    """
    store = next((chat[key] for key in ('max_store_id', 'last_store_id', 'store_id')
                  if key in chat), None)
    store = nonnegative_integer(store, 'READ_STATE_MISSING')
    if store == 0:
        raise ValueError('READ_STATE_MISSING')
    rows = [chat] if chats is None else chats
    mapped = {}
    for row in rows:
        identity = chat_id(row)
        if identity in mapped:
            raise ValueError('READ_CHAT_STATE_DUPLICATE')
        mapped[identity] = chat_type(row)
    if conversation not in mapped or chat_id(chat) != conversation:
        raise ValueError('READ_CHAT_STATE_MISSING')
    data = unread_response.get('data')
    counts = data.get('user_chat_unread_counts') if isinstance(data, dict) else None
    if not isinstance(counts, dict) or not counts or set(counts) != set(mapped):
        raise ValueError('READ_UNREAD_STATE_MISSING')
    remaining = {identity: nonnegative_integer(value, 'READ_UNREAD_STATE_INVALID')
                 for identity, value in counts.items()}
    remaining[conversation] = 0  # clearUnread(target), not a missing-state default.
    computed = dict(zip(GLOBAL_COUNTERS, (
        sum(remaining.values()),
        0,  # Public _reportMarkRead explicitly assigns this constant.
        int(any(mapped[key] == 2 and value > 0 for key, value in remaining.items())),
    )))
    if counters is not None and global_counters(counters) != computed:
        raise ValueError('READ_GLOBAL_STATE_CONFLICT')
    return ({'chat_id': conversation, 'read_store_id': store,
             'unread_count': 0, 'type': mapped[conversation], 'need_rm_offline': True},
            computed)
