{#- Asia/Kuala_Lumpur calendar date of a UTC timestamp (data contract: business date).
    Malaysia is UTC+8 with no daylight saving (ADR 0006), so a fixed offset on epoch seconds is
    exact and does not depend on the session time zone of the SQL warehouse. -#}
{% macro business_date(ts) -%}
date_from_unix_date(CAST((unix_seconds({{ ts }}) + 28800) div 86400 AS INT))
{%- endmacro %}
