ALTER TABLE web_presence_replies
ADD COLUMN source_event_id INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS
ux_web_presence_replies_source_event_id
ON web_presence_replies(source_event_id);
