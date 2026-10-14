# Adaptador de base de datos (`core.sqlite.*`)

Código: `pallaquino_cli/integrations/database.py`.

| Herramienta | Resultado |
|---|---|
| `core.sqlite.test_connection` | `{ok, sqlite_version}` |
| `core.sqlite.tables` | tablas y vistas |
| `core.sqlite.schema` | columnas (nombre, tipo, `not_null`, `primary_key`) y DDL |
| `core.sqlite.query` (`provides: sql_read`) | una sentencia con parámetros enlazados; `max_rows` ≤ 1000; marca `truncated` |

Todas son READ_ONLY y DATABASE_READ, sobre archivos `.db`, `.sqlite` o `.sqlite3` dentro del workspace.

## Solo lectura en tres capas

1. Se abre como `file:...?mode=ro` (URI).
2. Se ejecuta `PRAGMA query_only = ON`.
3. Un authorizer permite solo `SELECT`, `READ`, funciones, CTE recursivas y pragmas de introspección (`table_info`, `index_list`…).
   INSERT, UPDATE, DELETE, DDL, ATTACH y los pragmas de escritura los rechaza SQLite: `test_writes_are_refused_by_sqlite_itself` lo prueba
   también con `WITH … UPDATE`.

Un progress handler aplica la fecha límite y la cancelación de la pasarela.

## Fuera de 0.5.0

- Conexiones de escritura, migraciones y consultas destructivas. `database_migration_apply` sigue siendo gobernada.
- PostgreSQL y MySQL/MariaDB: se preparan mediante el protocolo `DatabaseAdapter` (`test_connection`, `tables`, `schema`,
  `query_read_only`), que un plugin de tipo DATABASE_CONNECTOR puede implementar. No se incluye ningún driver ni adaptador sin verificar.
