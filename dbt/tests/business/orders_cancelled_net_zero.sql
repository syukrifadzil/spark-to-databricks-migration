-- Contract rule orders.cancelled_net_zero: cancelled orders net to zero.
{{ config(severity='warn') }}

select order_id, charges, refunds
from {{ ref('int_order_balances') }}
where has_items
  and status = 'cancelled'
  and charges - refunds <> 0
