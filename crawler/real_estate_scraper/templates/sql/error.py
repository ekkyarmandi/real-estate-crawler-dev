error_insert_query = """
INSERT INTO listings_error (
    id,
    created_at,
    updated_at,
    url,
    error_type,
    error_message,
    error_traceback
) VALUES (
    uuid_generate_v4(),
    now(),
    now(),
    %(url)s,
    %(error_type)s,
    %(error_message)s,
    %(error_traceback)s
) ON CONFLICT (url, error_type, error_message) DO UPDATE SET updated_at = now();
"""
