-- Contract rule customers.updated_after_created: updated_at is not earlier than created_at.
{{ config(severity='warn') }}

select customer_id, created_at, updated_at
from {{ ref('stg_customers') }}
where updated_at < created_at
