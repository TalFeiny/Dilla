-- Delete dummy temp-company columns from matrix_columns (e.g. "col-1255353").
-- Match col- followed by digits only; real added columns use col-{timestamp}-{random} so they are not matched.
DELETE FROM matrix_columns
WHERE column_id ~* '^col-[0-9]+$'
   OR name ~* '^col-[0-9]+$';
