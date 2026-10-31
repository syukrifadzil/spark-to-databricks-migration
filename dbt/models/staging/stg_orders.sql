select
    order_id,
    customer_id,
    order_date,
    status,
    {{ business_date('order_date') }} as order_business_date,
    -- Sold order (data contract section 7): pending and cancelled orders are not sales.
    status in ('paid', 'shipped', 'delivered') as is_sold
from {{ source('silver', 'orders') }}
