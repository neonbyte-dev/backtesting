"""
Find pharoh, potter and other callers in Shocked Trading
"""
import clickhouse_connect

client = clickhouse_connect.get_client(
    host='ch.ops.xexlab.com',
    port=443,
    username='dev_ado',
    password='5tTq7p6HBvCH5m4E',
    database='crush_ats',
    secure=True
)

print("="*60)
print("SEARCHING FOR CALLERS")
print("="*60)

# Search for pharoh/potter across all channels
print("\n1. Searching for 'pharoh' or 'potter' in user names...")
search_query = """
SELECT DISTINCT
    user_name,
    chat_name,
    sub_chat_name,
    COUNT(*) as msg_count
FROM messages
WHERE lower(user_name) LIKE '%pharoh%'
   OR lower(user_name) LIKE '%potter%'
   OR lower(user_name) LIKE '%pharo%'
GROUP BY user_name, chat_name, sub_chat_name
ORDER BY msg_count DESC
"""
results = client.query(search_query)
print("\nResults:")
for row in results.result_rows:
    print(f"   User: {row[0]} | Chat: {row[1]} | SubChat: {row[2]} | Messages: {row[3]}")

# Check sub-channels in Shocked Trading
print("\n2. Sub-channels in Shocked Trading:")
subchat_query = """
SELECT
    sub_chat_name,
    COUNT(*) as msg_count,
    COUNT(DISTINCT user_name) as unique_users
FROM messages
WHERE chat_name = 'Shocked Trading'
GROUP BY sub_chat_name
ORDER BY msg_count DESC
"""
subchats = client.query(subchat_query)
print("\nSub-channels:")
for row in subchats.result_rows:
    print(f"   - {row[0] or '[main]'}: {row[1]} messages, {row[2]} users")

# Get all unique callers across ALL sub-channels in Shocked Trading
print("\n3. All callers in Shocked Trading (all sub-channels):")
all_callers_query = """
SELECT
    user_name,
    sub_chat_name,
    COUNT(*) as msg_count,
    countIf(raw LIKE '%pump%' OR raw LIKE '%1-9A-HJ-NP-Za-km-z%') as potential_calls
FROM messages
WHERE chat_name = 'Shocked Trading'
GROUP BY user_name, sub_chat_name
ORDER BY msg_count DESC
"""
all_callers = client.query(all_callers_query)
print("\nCallers by sub-channel:")
for row in all_callers.result_rows:
    print(f"   - {row[0]} [{row[1] or 'main'}]: {row[2]} messages")

# Sample messages from each sub-channel
print("\n4. Sample messages from each sub-channel:")
for subchat_row in subchats.result_rows[:5]:
    subchat = subchat_row[0]
    print(f"\n{'='*60}")
    print(f"SUB-CHANNEL: {subchat or '[main]'}")
    print("="*60)

    if subchat:
        sample_q = f"""
        SELECT user_name, raw, created_at
        FROM messages
        WHERE chat_name = 'Shocked Trading'
          AND sub_chat_name = '{subchat}'
        ORDER BY created_at DESC
        LIMIT 5
        """
    else:
        sample_q = """
        SELECT user_name, raw, created_at
        FROM messages
        WHERE chat_name = 'Shocked Trading'
          AND (sub_chat_name = '' OR sub_chat_name IS NULL)
        ORDER BY created_at DESC
        LIMIT 5
        """
    samples = client.query(sample_q)
    for msg in samples.result_rows:
        content = msg[1][:150].replace('\n', ' ')
        print(f"\n  [{msg[0]}] {msg[2]}:")
        print(f"  {content}...")
