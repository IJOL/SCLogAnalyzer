
CREATE OR REPLACE FUNCTION public.generate_hash(username text, killer text, victim text, t text)
 RETURNS text
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$DECLARE
    result TEXT;
BEGIN
    result := MD5(COALESCE(username, '') || COALESCE(killer, '') || COALESCE(victim, '') || COALESCE(t, ''));
    RETURN result;
END;$function$
;

CREATE OR REPLACE FUNCTION public.run_sql(query text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
      EXECUTE query;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.list_tables()
 RETURNS TABLE(table_name text)
 LANGUAGE sql
AS $function$
    select table_name
    from information_schema.tables
    where table_schema = 'public';
$function$
;