{{ config(materialized='ephemeral') }}

-- One row per order with its item total and succeeded money, for the business-rule tests.
-- Ephemeral: inlined into the tests that use it, so no object is created in retail_gold.
with items as (
    select order_id, sum(line_total) as order_total
    from {{ ref('stg_order_items') }}
    group by order_id
),

money as (
    select order_id,
           sum(case when payment_type = 'charge' then amount else 0 end) as charges,
           sum(case when payment_type = 'refund' then amount else 0 end) as refunds
    from {{ ref('stg_payments') }}
    where is_succeeded
    group by order_id
)

select
    o.order_id,
    o.customer_id,
    o.order_date,
    o.status,
    i.order_id is not null as has_items,
    coalesce(i.order_total, 0) as order_total,
    coalesce(m.charges, 0) as charges,
    coalesce(m.refunds, 0) as refunds
from {{ ref('stg_orders') }} as o
left join items as i on o.order_id = i.order_id
left join money as m on o.order_id = m.order_id
