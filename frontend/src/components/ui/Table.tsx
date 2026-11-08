import React from 'react';

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
  width?: string;
  isNumeric?: boolean;
}

export interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  className?: string;
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  emptyMessage = 'No records found.',
  onRowClick,
  className = '',
}: TableProps<T>) {
  return (
    <div className={`w-full overflow-x-auto border border-surface-200 rounded bg-white shadow-subtle ${className}`}>
      <table className="w-full border-collapse text-left text-base">
        <thead className="bg-surface-50 border-b border-surface-200 sticky top-0 z-10 select-none">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{ width: col.width }}
                className={`py-2 px-3 text-xs font-semibold text-surface-600 tracking-wider ${
                  col.align === 'right' || col.isNumeric
                    ? 'text-right'
                    : col.align === 'center'
                    ? 'text-center'
                    : 'text-left'
                }`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-200 text-surface-800">
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="py-8 px-4 text-center text-xs text-surface-400 font-medium"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item) => (
              <tr
                key={keyExtractor(item)}
                onClick={() => onRowClick && onRowClick(item)}
                className={`transition-colors ${
                  onRowClick
                    ? 'cursor-pointer hover:bg-surface-50 active:bg-surface-100'
                    : 'hover:bg-surface-50/50'
                }`}
              >
                {columns.map((col) => {
                  const content = col.render
                    ? col.render(item)
                    : (item as Record<string, any>)[col.key];

                  return (
                    <td
                      key={col.key}
                      className={`py-2 px-3 text-base ${
                        col.isNumeric ? 'tabular-nums text-right' : ''
                      } ${
                        col.align === 'right'
                          ? 'text-right'
                          : col.align === 'center'
                          ? 'text-center'
                          : 'text-left'
                      }`}
                    >
                      {content}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
