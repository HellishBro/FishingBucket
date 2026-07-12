ALTER TABLE autoproxies ADD COLUMN flags INTEGER;
UPDATE global_stats SET value = 16 WHERE key = 'version';