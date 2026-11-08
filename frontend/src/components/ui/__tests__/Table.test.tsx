import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Table, Column } from '../Table';

interface TestItem {
  id: string;
  name: string;
  count: number;
}

describe('Table Component', () => {
  const columns: Column<TestItem>[] = [
    { key: 'id', header: 'ID', width: '60px' },
    { key: 'name', header: 'Name' },
    { key: 'count', header: 'Count', isNumeric: true },
  ];

  const data: TestItem[] = [
    { id: '1', name: 'Item One', count: 42 },
    { id: '2', name: 'Item Two', count: 99 },
  ];

  it('renders headers and tabular rows correctly', () => {
    render(<Table columns={columns} data={data} keyExtractor={(i) => i.id} />);

    expect(screen.getByText('Item One')).toBeInTheDocument();
    expect(screen.getByText('Item Two')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('99')).toBeInTheDocument();
  });

  it('renders custom empty message when data is empty', () => {
    render(
      <Table
        columns={columns}
        data={[]}
        keyExtractor={(i) => i.id}
        emptyMessage="No guideline rules confirmed."
      />
    );

    expect(screen.getByText('No guideline rules confirmed.')).toBeInTheDocument();
  });

  it('triggers onRowClick when a row is clicked', () => {
    const handleRowClick = vi.fn();
    render(
      <Table
        columns={columns}
        data={data}
        keyExtractor={(i) => i.id}
        onRowClick={handleRowClick}
      />
    );

    fireEvent.click(screen.getByText('Item One'));
    expect(handleRowClick).toHaveBeenCalledWith(data[0]);
  });
});
