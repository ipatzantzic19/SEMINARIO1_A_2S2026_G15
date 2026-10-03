-- TaskFlow + CloudDrive - PRA2-1
-- Consultas de validación sin datos sensibles.

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('usuarios', 'tareas', 'archivos')
ORDER BY table_name;

SELECT table_name, constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'public'
  AND table_name IN ('usuarios', 'tareas', 'archivos')
ORDER BY table_name, constraint_name;

SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('usuarios', 'tareas', 'archivos')
ORDER BY tablename, indexname;

SELECT trigger_name, event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'public'
  AND event_object_table IN ('usuarios', 'tareas')
ORDER BY event_object_table, trigger_name;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('usuarios', 'tareas', 'archivos')
ORDER BY table_name, ordinal_position;
