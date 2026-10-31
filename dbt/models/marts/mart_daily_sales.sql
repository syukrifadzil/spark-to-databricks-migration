-- One row per business date with any order or any succeeded payment (data contract section 7).
-- Order measures use the order's business date; money uses the payment's business date.
with orders as (
    select * from {{ ref('stg_orders') }}
),

sold_lines as (
    select o.order_business_date as business_date, i.quantity, i.line_total
    from {{ ref('stg_order_items') }} as i
    inner join orders as o on i.order_id = o.order_id
    where o.is_sold
),

by_order_date as (
    select order_business_date as business_date,
           count(*) as orders_placed,
           count_if(is_sold) as orders_sold
    from orders
    group by order_business_date
),

by_line_date as (
    select business_date,
           sum(quantity) as items_sold,
           sum(line_total) as gross_sales
    from sold_lines
    group by business_date
),

by_payment_date as (
    select payment_business_date as business_date,
           sum(case when payment_type = 'charge' then amount else 0 end) as charges,
           sum(case when payment_type = 'refund' then amount else 0 end) as refunds
    from {{ ref('stg_payments') }}
    where is_succeeded
    group by payment_business_date
),

dates as (
    select business_date from by_order_date
    union
    select business_date from by_payment_date
)

select
    d.business_date,
    coalesce(o.orders_placed, 0) as orders_placed,
    coalesce(o.orders_sold, 0) as orders_sold,
    coalesce(l.items_sold, 0) as items_sold,
    cast(coalesce(l.gross_sales, 0) as decimal(18, 2)) as gross_sales,
    cast(coalesce(p.charges, 0) as decimal(18, 2)) as charges,
    cast(coalesce(p.refunds, 0) as decimal(18, 2)) as refunds,
    cast(coalesce(p.charges, 0) - coalesce(p.refunds, 0) as decimal(18, 2)) as net_payments
from dates as d
left join by_order_date as o on d.business_date = o.business_date
left join by_line_date as l on d.business_date = l.business_date
left join by_payment_date as p on d.business_date = p.business_date
