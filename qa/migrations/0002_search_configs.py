from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations

# Accent-insensitive text search configurations, so "securite" finds "sécurité".
CREATE = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'snpnca_fr') THEN
    CREATE TEXT SEARCH CONFIGURATION snpnca_fr (COPY = french);
    ALTER TEXT SEARCH CONFIGURATION snpnca_fr
      ALTER MAPPING FOR hword, hword_part, word WITH unaccent, french_stem;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'snpnca_en') THEN
    CREATE TEXT SEARCH CONFIGURATION snpnca_en (COPY = english);
    ALTER TEXT SEARCH CONFIGURATION snpnca_en
      ALTER MAPPING FOR hword, hword_part, word WITH unaccent, english_stem;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'snpnca_simple') THEN
    CREATE TEXT SEARCH CONFIGURATION snpnca_simple (COPY = simple);
    ALTER TEXT SEARCH CONFIGURATION snpnca_simple
      ALTER MAPPING FOR hword, hword_part, word WITH unaccent, simple;
  END IF;
END
$$;
"""

DROP = """
DROP TEXT SEARCH CONFIGURATION IF EXISTS snpnca_fr;
DROP TEXT SEARCH CONFIGURATION IF EXISTS snpnca_en;
DROP TEXT SEARCH CONFIGURATION IF EXISTS snpnca_simple;
"""


class Migration(migrations.Migration):
    dependencies = [("qa", "0001_initial")]

    operations = [
        UnaccentExtension(),
        migrations.RunSQL(CREATE, DROP),
    ]
