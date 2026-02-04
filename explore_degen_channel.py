"""
Explore the degen channel data in Clickhouse to understand structure and identify callers
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
print("EXPLORING DEGEN CHANNEL DATA")
print("="*60)

# Check the messages table structure first
print("\n1. Messages table structure:")
schema = client.query("DESCRIBE messages")
for row in schema.result_rows:
    print(f"   - {row[0]}: {row[1]}")

# Get distinct channels
print("\n2. All channels:")
channels_query = """
SELECT DISTINCT chat_name, COUNT(*) as msg_count
FROM messages
GROUP BY chat_name
ORDER BY msg_count DESC
"""
channels = client.query(channels_query)
print("\nChannels found:")
for row in channels.result_rows:
    print(f"   - {row[0]}: {row[1]:,} messages")

# Look for degen-related channels
print("\n3. Searching for 'degen' channels...")
degen_query = """
SELECT DISTINCT chat_name, COUNT(*) as msg_count
FROM messages
WHERE lower(chat_name) LIKE '%degen%'
GROUP BY chat_name
ORDER BY msg_count DESC
"""
degen_channels = client.query(degen_query)
print("Degen channels found:")
for row in degen_channels.result_rows:
    print(f"   - {row[0]}: {row[1]:,} messages")

# Get all authors in degen channels
print("\n4. Authors in degen channels:")
authors_query = """
SELECT
    author_name,
    COUNT(*) as msg_count,
    MIN(timestamp) as first_msg,
    MAX(timestamp) as last_msg
FROM messages
WHERE lower(chat_name) LIKE '%degen%'
GROUP BY author_name
ORDER BY msg_count DESC
LIMIT 30
"""
authors = client.query(authors_query)
print(f"\nTop authors by message count:")
for row in authors.result_rows:
    print(f"   - {row[0]}: {row[1]:,} messages ({row[2]} to {row[3]})")

# Sample messages from top authors to understand signal patterns
print("\n5. Sample messages from top 5 authors:")
for author_row in authors.result_rows[:5]:
    author = author_row[0]
    print(f"\n--- {author} ---")
    sample_query = f"""
    SELECT content, timestamp
    FROM messages
    WHERE lower(chat_name) LIKE '%degen%'
      AND author_name = '{author}'
    ORDER BY timestamp DESC
    LIMIT 5
    """
    samples = client.query(sample_query)
    for msg in samples.result_rows:
        content = msg[0][:150].replace('\n', ' ') + "..." if len(msg[0]) > 150 else msg[0].replace('\n', ' ')
        print(f"  [{msg[1]}]: {content}")
