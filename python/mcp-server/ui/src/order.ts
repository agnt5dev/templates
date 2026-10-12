// The order view: an MCP App that clients rendering MCP Apps (ChatGPT,
// Claude, Cursor, VS Code) show for lookup_order's results. The host hands it
// the tool's result over the MCP Apps bridge; it makes no network requests.

import {
  App,
  applyDocumentTheme,
  applyHostStyleVariables,
  type McpUiHostContext,
} from '@modelcontextprotocol/ext-apps';

/** lookup_order's result: its structuredContent. */
interface Order {
  id: string;
  customer: string;
  item: string;
  total: number;
  status: string;
}

const $ = (id: string) => document.getElementById(id) as HTMLElement;

function isOrder(value: unknown): value is Order {
  const order = value as Partial<Order> | null;
  return typeof order?.id === 'string' && typeof order.total === 'number';
}

function show(order: Order): void {
  $('id').textContent = `Order ${order.id}`;
  $('status').textContent = order.status;
  $('status').hidden = false;
  $('customer').textContent = order.customer;
  $('item').textContent = order.item;
  $('total').textContent = order.total.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
  $('details').hidden = false;
  $('note').hidden = true;
}

function note(text: string): void {
  $('details').hidden = true;
  $('status').hidden = true;
  $('note').textContent = text;
  $('note').hidden = false;
}

function applyContext(context: McpUiHostContext | undefined): void {
  if (context?.theme) applyDocumentTheme(context.theme);
  if (context?.styles?.variables) applyHostStyleVariables(context.styles.variables);
}

const app = new App({ name: 'order', version: '0.1.0' });

app.ontoolinput = (params) => {
  const orderId = (params.arguments as Record<string, unknown> | undefined)?.orderId
    ?? (params.arguments as Record<string, unknown> | undefined)?.order_id;
  if (typeof orderId === 'string') note(`Looking up ${orderId}…`);
};

app.ontoolresult = (result) => {
  if (!result.isError && isOrder(result.structuredContent)) {
    show(result.structuredContent);
    return;
  }
  // A failed call (an unknown order id, say) carries its reason as text.
  const text = (result.content ?? []).map((c) => (c.type === 'text' ? c.text : '')).join('\n');
  note(text || 'No order to show.');
};

app.onhostcontextchanged = (context) => applyContext(context as McpUiHostContext);

await app.connect();
applyContext(app.getHostContext());
