/**
 * Stand-in data so the template runs without a real order system.
 *
 * Swap `ORDERS` and `POLICIES` for calls to your own systems; keep the shapes.
 */

export interface Order {
  order_id: string;
  item: string;
  amount_usd: number;
  status: string;
}

// Refunds above this amount (USD) wait for a human to approve them.
export const APPROVAL_THRESHOLD_USD = 100;

export const ORDERS: Record<string, Order> = {
  'ORD-1001': { order_id: 'ORD-1001', item: 'USB-C cable', amount_usd: 45, status: 'delivered' },
  'ORD-2002': { order_id: 'ORD-2002', item: 'Noise-cancelling headphones', amount_usd: 250, status: 'delivered' },
  'ORD-3003': { order_id: 'ORD-3003', item: 'Laptop stand', amount_usd: 80, status: 'shipped' },
};

export const POLICIES: Record<string, string> = {
  refund: 'Refunds go back to the original payment method within 5 business days.',
  bug: 'Our engineers review bug reports within one business day.',
  question: 'Our help center at help.example.com answers most account questions.',
};

export const REFUND_WORDS = ['refund', 'money back', 'charged'];
export const BUG_WORDS = ['error', 'crash', 'broken', 'bug'];
export const URGENT_WORDS = ['urgent', 'asap', 'immediately'];
