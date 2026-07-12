ALTER TABLE user_settings ADD COLUMN spotlight TEXT;
UPDATE global_stats SET value = 15 WHERE key = 'version';