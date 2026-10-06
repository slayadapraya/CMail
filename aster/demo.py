from datetime import datetime, timedelta, timezone

def seed(store):
    if store.get('seeded'): return
    now = datetime.now(timezone.utc)
    rows = []
    samples = [
        ('Maya Chen', 'maya@example.com', 'Design studio · tomorrow’s session', 'Hey! Bring your sketches to studio tomorrow. We’ll spend the first half reviewing concepts, then work in small groups.\n\nSee you at 10,\nMaya', False),
        ('Student Services', 'services@example.com', 'Your week on campus', 'A few things happening this week:\n\nTuesday: careers drop-in, 12–2 pm\nThursday: clubs fair, main courtyard\nFriday: library late opening\n\nThese are fictional demo messages.', False),
        ('Alex Rivera', 'alex@example.com', 'Re: The group project', 'The shared outline looks good. I can take the research section. Shall we meet after class to pull everything together?', True),
        ('Library', 'library@example.com', 'A little reminder about your books', 'Your borrowed books are due next week. You can renew them through the library portal.\n\nThis message is sample data.', True),
        ('Jordan Lee', 'jordan@example.com', 'Coffee after class?', 'I’ll be at the café around 3. Let me know if you’re free!', True),
    ]
    for i, (name, address, subject, body, read) in enumerate(samples):
        rows.append({'id': 'demo-' + str(i), 'subject': subject, 'from': {'emailAddress': {'name': name, 'address': address}}, 'receivedDateTime': (now - timedelta(hours=i * 3)).isoformat(), 'isRead': read, 'hasAttachments': False, 'bodyPreview': body, 'body': {'contentType': 'Text', 'content': body}})
    store.replace('mail', 'inbox', rows)
    store.replace('contacts', '', [{'id': str(i), 'displayName': name, 'emailAddresses': [{'name': name, 'address': address}]} for i, (name, address, *_) in enumerate(samples)])
    store.set('seeded', True)

def events(year, month):
    return [dict(id='demo-event-' + str(day), subject=title, start={'dateTime': datetime(year, month, day, hour).astimezone().astimezone(timezone.utc).isoformat(), 'timeZone': 'UTC'}, end={'dateTime': datetime(year, month, day, hour + 1).astimezone().astimezone(timezone.utc).isoformat(), 'timeZone': 'UTC'}, location={'displayName': room}) for day, hour, title, room in [(8, 10, 'Design studio', 'Room 204'), (14, 14, 'Project catch-up', 'Library'), (22, 12, 'Careers drop-in', 'Student hub')]]
