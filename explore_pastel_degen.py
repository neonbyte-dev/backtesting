"""
Explore Pastel Degen channel - understand caller → Rick bot flow
"""
import clickhouse_connect
import pandas as pd
from datetime import timedelta

client = clickhouse_connect.get_client(
    host='ch.ops.xexlab.com',
    port=443,
    username='dev_ado',
    password='5tTq7p6HBvCH5m4E',
    database='crush_ats',
    secure=True
)

print("="*70)
print("EXPLORING PASTEL DEGEN CHANNEL")
print("="*70)

# Get all messages ordered by time
query = """
SELECT
    user_name,
    raw,
    created_at,
    message_id
FROM messages
WHERE chat_name = 'Pastel'
  AND sub_chat_name = '❗｜degen'
  AND raw != ''
ORDER BY created_at ASC
"""
result = client.query(query)
messages = pd.DataFrame(result.result_rows, columns=['caller', 'content', 'timestamp', 'message_id'])
print(f"\nTotal messages: {len(messages)}")

# Show callers
print("\nCallers:")
for caller, count in messages['caller'].value_counts().items():
    print(f"   - {caller}: {count}")

# Look at Rick bot messages specifically
print("\n" + "="*70)
print("RICK BOT MESSAGE FORMAT")
print("="*70)

rick_messages = messages[messages['caller'].str.contains('Rick', case=False, na=False)]
print(f"\nRick bot messages: {len(rick_messages)}")

print("\nSample Rick bot messages:")
for i, (_, row) in enumerate(rick_messages.head(10).iterrows()):
    print(f"\n[{row['timestamp']}]")
    print(row['content'][:500])
    print("-"*50)

# Look at the sequence: caller posts address → Rick responds
print("\n" + "="*70)
print("CALLER → RICK BOT SEQUENCE ANALYSIS")
print("="*70)

# Find messages just before Rick bot messages
print("\nLooking at what comes before Rick bot alerts...")

for i, (idx, rick_row) in enumerate(rick_messages.head(20).iterrows()):
    rick_time = rick_row['timestamp']
    rick_content = rick_row['content']

    # Find messages in the 60 seconds before Rick's message
    time_window = timedelta(seconds=60)
    before_msgs = messages[
        (messages['timestamp'] < rick_time) &
        (messages['timestamp'] > rick_time - time_window) &
        (~messages['caller'].str.contains('Rick|bot', case=False, na=False))
    ]

    if len(before_msgs) > 0:
        print(f"\n{'='*60}")
        print(f"RICK BOT [{rick_time}]:")
        print(f"  {rick_content[:200]}...")
        print(f"\nPRECEDING MESSAGES:")
        for _, prev in before_msgs.iterrows():
            print(f"  [{prev['caller']}] {prev['timestamp']}:")
            print(f"    {prev['content'][:150]}")
