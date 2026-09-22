// Expressions match the governed order_metrics cube and monthly_order_summary view.
export const months = ['2018-01', '2018-02', '2018-03', '2018-04'];
export const statuses = ['completed', 'placed', 'returned', 'return_pending', 'shipped'];
export const measures = `COUNT(*) AS order_count,
  COUNT(DISTINCT customer_id) AS purchasing_customers,
  SUM(amount) AS total_order_amount,
  AVG(amount) AS average_order_value,
  SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) AS completed_order_amount`;
export function queries(month = '', status = '') {
  if (month && !months.includes(month)) throw new Error('Unknown snapshot month');
  if (status && !statuses.includes(status)) throw new Error('Unknown order status');
  const conditions = [];
  if (month) {
    const next = `2018-${String(Number(month.slice(-2)) + 1).padStart(2, '0')}-01`;
    conditions.push(`order_date >= DATE '${month}-01' AND order_date < DATE '${next}'`);
  }
  if (status) conditions.push(`status = '${status}'`);
  const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
  const orderWhere = where.replaceAll('order_date', 'o.order_date').replaceAll('status =', 'o.status =');
  return {
    inventory: 'SELECT COUNT(*) AS customer_count FROM customers',
    payments: 'SELECT COUNT(*) AS payment_count FROM payments',
    kpis: `SELECT ${measures}\nFROM orders ${where}`,
    monthly: !status
      ? `SELECT order_month, order_count, purchasing_customers, total_order_amount, average_order_value, completed_order_amount\nFROM monthly_order_summary${month ? ` WHERE order_month = DATE '${month}-01'` : ''}\nORDER BY order_month`
      : `SELECT DATE_TRUNC('month', order_date) AS order_month, ${measures}\nFROM orders ${where}\nGROUP BY DATE_TRUNC('month', order_date)\nORDER BY order_month`,
    customers: `SELECT c.customer_id, c.first_name, c.last_name, COUNT(*) AS order_count, SUM(o.amount) AS total_order_amount\nFROM orders o JOIN customers c ON o.customer_id = c.customer_id\n${orderWhere}\nGROUP BY c.customer_id, c.first_name, c.last_name\nORDER BY total_order_amount DESC, c.customer_id ASC\nLIMIT 10`,
    status: `SELECT status, COUNT(*) AS order_count, SUM(amount) AS total_order_amount\nFROM orders ${where}\nGROUP BY status\nORDER BY total_order_amount DESC, status`,
    orphanOrders: 'SELECT COUNT(*) AS issues FROM orders o LEFT JOIN customers c ON o.customer_id = c.customer_id WHERE c.customer_id IS NULL',
    orphanPayments: 'SELECT COUNT(*) AS issues FROM payments p LEFT JOIN orders o ON p.order_id = o.order_id WHERE o.order_id IS NULL',
    mismatches: `WITH payment_totals AS (SELECT order_id, SUM(amount) AS payment_amount FROM payments GROUP BY order_id)
SELECT COUNT(*) AS issues FROM orders o
LEFT JOIN payment_totals pt ON o.order_id = pt.order_id
WHERE ABS(o.amount - pt.payment_amount) > 0.000001
   OR (o.amount IS NULL AND pt.payment_amount IS NOT NULL)
   OR (o.amount IS NOT NULL AND pt.payment_amount IS NULL)`
  };
}
