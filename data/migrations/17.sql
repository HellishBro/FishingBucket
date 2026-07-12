ALTER TABLE user_settings ADD COLUMN private_spotlight BOOLEAN;
UPDATE global_stats SET value = 17 WHERE key = 'version';