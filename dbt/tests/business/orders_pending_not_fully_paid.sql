-- Contract rule orders.pending_not_fully_paid: pending orders are unpaid or partially paid.
{{ config(severity='warn') }}

select order_id, charges, order_total
from {{ ref('int_order_balances') }}
where has_items
  and status = 'pending'
  and charges >= order_total
