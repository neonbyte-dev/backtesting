"""
Explore Shocked Trading channel - identify callers and message patterns
"""
import clickhouse_connect
import pandas as pd

# Connect to Clickhouse
client = clickhouse_connect.get_client(
    host='ch.ops.xexlab.com',
    port=443,
    username='dev_ado',
    password='5tTq7p6HBvCH5m4E',
    database='crush_ats',
    secure=True
)

print("="*60)
print("EXPLORING SHOCKED TRADING CHANNEL")
print("="*60)

# Check which fields have content
print("\n1. Checking which fields have content:")
check_query = """
SELECT
    COUNT(*) as total,
    countIf(message_content != '') as has_message_content,
    countIf(raw != '') as has_raw,
    countIf(raw_html != '') as has_raw_html
FROM messages
WHERE chat_name = 'Shocked Trading'
"""
check = client.query(check_query)
for row in check.result_rows:
    print(f"   Total: {row[0]}")
    print(f"   Has message_content: {row[1]}")
    print(f"   Has raw: {row[2]}")
    print(f"   Has raw_html: {row[3]}")

# Get callers with message counts
print("\n2. Callers in Shocked Trading:")
callers_query = """
SELECT
    user_name,
    COUNT(*) as msg_count,
    MIN(created_at) as first_msg,
    MAX(created_at) as last_msg
FROM messages
WHERE chat_name = 'Shocked Trading'
GROUP BY user_name
ORDER BY msg_count DESC
"""
callers = client.query(callers_query)
print(f"\nCallers by message count:")
for row in callers.result_rows:
    print(f"   - {row[0]}: {row[1]:,} messages ({str(row[2])[:10]} to {str(row[3])[:10]})")

# Sample messages using raw field
print("\n3. Sample messages from each caller (using 'raw' field):")
for caller_row in callers.result_rows[:5]:  # Top 5 callers
    caller = caller_row[0]
    msg_count = caller_row[1]
    print(f"\n{'='*60}")
    print(f"CALLER: {caller} ({msg_count} messages)")
    print("="*60)

    # Escape single quotes in caller name
    caller_escaped = caller.replace("'", "''")
    sample_query = f"""
    SELECT raw, created_at
    FROM messages
    WHERE chat_name = 'Shocked Trading'
      AND user_name = '{caller_escaped}'
      AND raw != ''
    ORDER BY created_at DESC
    LIMIT 10
    """
    samples = client.query(sample_query)
    if not samples.result_rows:
        print("  [No messages with content found]")
    for i, msg in enumerate(samples.result_rows, 1):
        content = msg[0][:300].replace('\n', ' ') if msg[0] else "[empty]"
        if len(msg[0] or "") > 300:
            content += "..."
        print(f"\n  [{msg[1]}]:")
        print(f"  {content}")

# Get date range
print("\n\n4. Data date range:")
range_query = """
SELECT
    MIN(created_at) as first_msg,
    MAX(created_at) as last_msg,
    COUNT(*) as total,
    countIf(raw != '') as with_content
FROM messages
WHERE chat_name = 'Shocked Trading'
"""
date_range = client.query(range_query)
for row in date_range.result_rows:
    print(f"   From: {row[0]}")
    print(f"   To: {row[1]}")
    print(f"   Total messages: {row[2]}")
    print(f"   With content: {row[3]}")
