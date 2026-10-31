select
    product_id,
    product_name,
    category,
    price,
    status
from {{ source('silver', 'products') }}
