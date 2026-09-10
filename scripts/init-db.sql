-- Digital Healthcare Services Platform Database Initialization
-- Required PostgreSQL extensions

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- btree_gist is REQUIRED for PostgreSQL exclusion constraints preventing double-booking across slot ranges (RUL-01)
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Initial verification notice
DO $$
BEGIN
  RAISE NOTICE 'Healthcare Platform DB extensions (uuid-ossp, btree_gist) initialized successfully.';
END $$;
