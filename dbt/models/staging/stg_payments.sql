select
    payment_id,
    order_id,
    payment_type,
    amount,
    method,
    status,
    payment_at,
    {{ business_date('payment_at') }} as payment_business_date,
    -- Only succeeded payments move money (data contract section 4).
    status = 'succeeded' as is_succeeded
from {{ source('silver', 'payments') }}
