select
    customer_id,
    name,
    email,
    region,
    created_at,
    updated_at
from {{ source('silver', 'customers') }}
