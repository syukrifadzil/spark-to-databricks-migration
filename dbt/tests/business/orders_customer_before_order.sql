-- Contract rule orders.customer_before_order: the customer existed before the order was placed.
-- Orders for customers missing from silver are covered by the relationship test instead.
{{ config(severity='warn') }}

select o.order_id, o.order_date, c.created_at
from {{ ref('int_order_balances') }} as o
inner join {{ ref('stg_customers') }} as c on o.customer_id = c.customer_id
where o.has_items
  and c.created_at > o.order_date
