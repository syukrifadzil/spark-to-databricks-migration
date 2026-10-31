-- One row per product, including products never sold (data contract section 7).
with sold_lines as (
    select i.product_id, i.order_id, i.quantity, i.line_total
    from {{ ref('stg_order_items') }} as i
    inner join {{ ref('stg_orders') }} as o on i.order_id = o.order_id
    where o.is_sold
),

product_sales as (
    select product_id,
           sum(quantity) as units_sold,
           sum(line_total) as gross_sales,
           count(distinct order_id) as orders_sold
    from sold_lines
    group by product_id
)

select
    p.product_id,
    p.product_name,
    p.category,
    p.status,
    coalesce(s.units_sold, 0) as units_sold,
    cast(coalesce(s.gross_sales, 0) as decimal(18, 2)) as gross_sales,
    coalesce(s.orders_sold, 0) as orders_sold
from {{ ref('stg_products') }} as p
left join product_sales as s on p.product_id = s.product_id
