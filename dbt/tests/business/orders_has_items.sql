-- Contract rule orders.has_items: every order has at least one item.
-- Business-rule tests warn rather than fail: a violation is a source data problem to report, not a
-- defect in the models. The order-level rules below skip orders without items, as the validator does.
{{ config(severity='warn') }}

select order_id
from {{ ref('int_order_balances') }}
where not has_items
