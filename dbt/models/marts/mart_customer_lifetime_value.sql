-- One row per customer, including customers with no orders (data contract section 7).
-- Orders for customers missing from silver are not attributed to anyone, as in the legacy job.
with sold as (
    select * from {{ ref('stg_orders') }} where is_sold
),

customer_orders as (
    select customer_id,
           min(order_business_date) as first_order_date,
           max(order_business_date) as last_order_date,
           count(*) as orders_sold
    from sold
    group by customer_id
),

customer_sales as (
    select o.customer_id, sum(i.line_total) as lifetime_gross_sales
    from {{ ref('stg_order_items') }} as i
    inner join sold as o on i.order_id = o.order_id
    group by o.customer_id
),

-- Net paid covers all of a customer's orders, whatever their status.
customer_net_paid as (
    select o.customer_id,
           sum(case when p.payment_type = 'charge' then p.amount else -p.amount end) as lifetime_net_paid
    from {{ ref('stg_payments') }} as p
    inner join {{ ref('stg_orders') }} as o on p.order_id = o.order_id
    where p.is_succeeded
    group by o.customer_id
)

select
    c.customer_id,
    c.region,
    co.first_order_date,
    co.last_order_date,
    coalesce(co.orders_sold, 0) as orders_sold,
    cast(coalesce(cs.lifetime_gross_sales, 0) as decimal(18, 2)) as lifetime_gross_sales,
    cast(coalesce(cn.lifetime_net_paid, 0) as decimal(18, 2)) as lifetime_net_paid
from {{ ref('stg_customers') }} as c
left join customer_orders as co on c.customer_id = co.customer_id
left join customer_sales as cs on c.customer_id = cs.customer_id
left join customer_net_paid as cn on c.customer_id = cn.customer_id
