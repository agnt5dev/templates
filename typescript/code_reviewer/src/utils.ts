type AdfNode = Record<string, any> | any[] | string | null | undefined;

export function parseAdf(node: AdfNode): string {
  if (Array.isArray(node)) {
    return node.map(parseAdf).join('');
  }
  if (typeof node === 'object' && node !== null) {
    const nodeType = node.type as string | undefined;
    if (nodeType === 'paragraph') {
      return (node.content ?? []).map(parseAdf).join('') + '\n';
    }
    if (nodeType === 'text') {
      let text: string = node.text ?? '';
      for (const mark of node.marks ?? []) {
        if (mark.type === 'strong') text = `**${text}**`;
        else if (mark.type === 'code') text = `\`${text}\``;
      }
      return text;
    }
    if (nodeType === 'bulletList') {
      return (node.content ?? []).map((item: AdfNode) => '- ' + parseAdf(item)).join('');
    }
    if (nodeType === 'orderedList') {
      return (node.content ?? []).map((item: AdfNode, i: number) => `${i + 1}. ${parseAdf(item).trim()}`).join('\n') + '\n';
    }
    if (nodeType === 'listItem') {
      return (node.content ?? []).map(parseAdf).join('');
    }
    if ('content' in node) {
      return (node.content ?? []).map(parseAdf).join('');
    }
  }
  return '';
}
