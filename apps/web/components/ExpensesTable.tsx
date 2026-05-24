import type { Expense } from '@/lib/types';
import { CATEGORY_LABELS_RU } from '@/lib/types';
import { formatAmount, formatDate } from '@/lib/format';
import { Table, TBody, TD, TH, THead, TR } from './ui/table';

const SOURCE_LABEL: Record<Expense['source'], string> = {
  bot_photo: '📷 фото',
  bot_text: '⌨ текст',
  admin_web: '🖥 веб',
};

export function ExpensesTable({ expenses }: { expenses: Expense[] }) {
  if (expenses.length === 0) {
    return <div className="p-6 text-muted-fg text-sm">Нет расходов под текущие фильтры.</div>;
  }
  return (
    <Table>
      <THead>
        <TR>
          <TH>Дата</TH>
          <TH>Категория</TH>
          <TH className="text-right">Сумма</TH>
          <TH>Описание</TH>
          <TH>Источник</TH>
        </TR>
      </THead>
      <TBody>
        {expenses.map((e) => (
          <TR key={e.id}>
            <TD className="whitespace-nowrap">{formatDate(e.paid_at)}</TD>
            <TD>{CATEGORY_LABELS_RU[e.category] || e.category}</TD>
            <TD className="text-right font-mono">{formatAmount(e.amount_minor, e.currency)}</TD>
            <TD className="text-muted-fg">{e.description || '—'}</TD>
            <TD className="text-muted-fg whitespace-nowrap">{SOURCE_LABEL[e.source]}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
