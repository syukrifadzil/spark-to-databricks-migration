select
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    cast(quantity * unit_price as decimal(18, 2)) as line_total
from {{ source('silver', 'order_items') }}
