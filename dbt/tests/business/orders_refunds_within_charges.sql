-- Contract rule orders.refunds_within_charges: succeeded refunds never exceed succeeded charges.
{{ config(severity='warn') }}

select order_id, charges, refunds
from {{ ref('int_order_balances') }}
where has_items
  and refunds > charges
