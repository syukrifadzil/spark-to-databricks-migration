-- Contract rule payments.after_order: payment_at is not earlier than the order's order_date.
{{ config(severity='warn') }}

select p.payment_id, p.payment_at, o.order_date
from {{ ref('stg_payments') }} as p
inner join {{ ref('stg_orders') }} as o on p.order_id = o.order_id
where p.payment_at < o.order_date
