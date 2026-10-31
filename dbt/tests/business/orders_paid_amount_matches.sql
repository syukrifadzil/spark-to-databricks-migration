-- Contract rule orders.paid_amount_matches: paid, shipped and delivered orders have succeeded
-- charges equal to the order total.
{{ config(severity='warn') }}

select order_id, status, charges, order_total
from {{ ref('int_order_balances') }}
where has_items
  and status in ('paid', 'shipped', 'delivered')
  and charges <> order_total
