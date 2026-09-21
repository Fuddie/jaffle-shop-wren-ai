# Jaffle Shop business rules

- Use customers, orders, and payments as the canonical business models. Raw seeds and staging duplicates are not additional business entities.
- All modeled amounts are AUD. payments maps to stg_payments, which already divides raw cents by 100.
- customers has one row per customer; orders one row per order; payments one row per payment.
- Join orders.customer_id to customers.customer_id and payments.order_id to orders.order_id. These relationships are supported by the upstream dbt definitions.
- Total order amount is SUM(orders.amount), across all statuses and payment methods, including coupons and gift cards. It is not net revenue or refund-adjusted revenue.
- Average order value is AVG(orders.amount). NULL amounts are excluded; monitor missing payment amounts.
- Completed order amount includes only status = 'completed'. Returned orders have no explicit refund transactions here; do not infer a refund amount.
- Purchasing customers is COUNT(DISTINCT orders.customer_id) in the selected period. It is not additive across months or statuses.
- Count orders and sum order amounts at order grain. Joining payments can multiply order rows; aggregate payments per order before combining order metrics.
- Customer lifetime values and order counts are lifetime measures; do not sum them after joining customers to orders or payments. NULL customer order counts and lifetime values indicate no matching activity and may be displayed as zero.
- Dates are UTC dates per upstream documentation. Group monthly summaries by order_date.
